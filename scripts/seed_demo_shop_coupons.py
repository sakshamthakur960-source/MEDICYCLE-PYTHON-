"""Safely seed the ten simulated pharmacy-app coupons into the existing Reward table.

Default mode is read-only. Use --apply to insert only missing offers. Existing
rows are never updated or deleted, and this script never creates or alters tables.
"""
from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from Database import engine
from models import Reward


OFFERS = [
    ("Tata 1mg", "₹20 off", "100.00"),
    ("Tata 1mg", "₹40 off", "200.00"),
    ("Tata 1mg", "₹60 off", "300.00"),
    ("Tata 1mg", "₹100 off", "500.00"),
    ("Tata 1mg", "₹150 off", "750.00"),
    ("PharmEasy", "₹20 off", "100.00"),
    ("PharmEasy", "₹40 off", "200.00"),
    ("PharmEasy", "₹60 off", "300.00"),
    ("PharmEasy", "₹100 off", "500.00"),
    ("PharmEasy", "₹150 off", "750.00"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Insert missing offers. Without this flag, perform a read-only preview.",
    )
    args = parser.parse_args()

    database_name = engine.url.database
    if database_name != "medicycle":
        raise SystemExit(
            f"Refusing to continue: expected database 'medicycle', got {database_name!r}."
        )

    inserted = 0
    existing = 0
    conflicts = 0
    with Session(engine) as session:
        for partner, discount, credits in OFFERS:
            title = f"MediCycle Demo Coupon - {discount}"
            description = (
                f"SIMULATED DEMO OFFER: {discount} on {partner}. "
                "Internal MediCycle prototype voucher only; this is not a real "
                "pharmacy promo code and cannot be applied to an external order."
            )
            match = session.scalar(
                select(Reward).where(
                    Reward.partnerName == partner,
                    Reward.title == title,
                ).limit(1)
            )
            if match is not None:
                if str(match.creditsRequired) != credits or match.status.lower() != "available":
                    conflicts += 1
                    print(
                        f"CONFLICT (left unchanged): {partner} / {title} "
                        f"(existing cost={match.creditsRequired}, status={match.status})"
                    )
                else:
                    existing += 1
                    print(f"EXISTS (unchanged): {partner} / {title}")
                continue

            print(f"{'INSERT' if args.apply else 'WOULD INSERT'}: {partner} / {title} / {credits} MC")
            if args.apply:
                session.add(
                    Reward(
                        partnerName=partner,
                        title=title,
                        description=description,
                        creditsRequired=credits,
                        status="AVAILABLE",
                        validUntil=None,
                        imagePath=None,
                    )
                )
                inserted += 1

        if args.apply:
            session.commit()
        else:
            session.rollback()

    print(f"Offers defined: {len(OFFERS)}")
    print(f"Inserted: {inserted}")
    print(f"Already present: {existing}")
    print(f"Conflicts left unchanged: {conflicts}")
    if not args.apply:
        print("Preview only. Re-run with --apply to insert missing offers.")


if __name__ == "__main__":
    main()
