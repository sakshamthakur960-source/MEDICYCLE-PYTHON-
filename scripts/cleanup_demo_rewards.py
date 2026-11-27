"""Safely remove demo rewards from MediCycle's catalogue.

Default mode is a read-only dry run. Use --apply only after taking a database backup.
Unredeemed demo rewards are deleted. Rewards referenced by redemption history are
retained but marked INACTIVE so historical records and foreign keys remain valid.
"""
from __future__ import annotations

import argparse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from Database import engine
from models import Reward, RewardRedemption


def find_demo_rewards(session: Session):
    redemption_count = func.count(RewardRedemption.redemptionId).label("redemption_count")
    return session.execute(
        select(Reward, redemption_count)
        .outerjoin(RewardRedemption, RewardRedemption.rewardId == Reward.rewardId)
        .where(
            or_(
                func.lower(Reward.partnerName) == "demo partner",
                func.lower(Reward.title).like("demo voucher%"),
            )
        )
        .group_by(Reward.rewardId)
        .order_by(Reward.createdAt, Reward.title)
    ).all()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean demo reward records safely.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, the script only reports matching records.",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        rows = find_demo_rewards(session)
        print(f"Demo reward records found: {len(rows)}")
        if not rows:
            return

        for reward, redemption_count in rows:
            action = "KEEP + DEACTIVATE" if redemption_count else "DELETE"
            print(
                f"{action}: id={reward.rewardId} | partner={reward.partnerName!r} "
                f"| title={reward.title!r} | redemption references={redemption_count}"
            )

        if not args.apply:
            print("\nDry run only. Back up the database, then rerun with --apply to proceed.")
            return

        deleted = 0
        deactivated = 0
        for reward, redemption_count in rows:
            if redemption_count:
                reward.status = "INACTIVE"
                deactivated += 1
            else:
                session.delete(reward)
                deleted += 1

        session.commit()
        print(
            f"Completed: {deleted} unredeemed demo rewards deleted; "
            f"{deactivated} reward(s) with redemption history retained as INACTIVE."
        )


if __name__ == "__main__":
    main()
