"""Idempotently add the initial 25 generic medicines to the MediCycle catalogue.

This script inserts only missing catalogue entries. It does not modify existing
medicines, batches, returns, or any schema objects.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from Database import engine
from models import Medicine


CATALOGUE = [
    ("Paracetamol", "Paracetamol", "500 mg", "Tablet", "Analgesic / antipyretic"),
    ("Ibuprofen", "Ibuprofen", "200 mg", "Tablet", "NSAID"),
    ("Cetirizine", "Cetirizine", "10 mg", "Tablet", "Antihistamine"),
    ("Loratadine", "Loratadine", "10 mg", "Tablet", "Antihistamine"),
    ("Aspirin", "Acetylsalicylic acid", "75 mg", "Tablet", "Antiplatelet"),
    ("Omeprazole", "Omeprazole", "20 mg", "Capsule", "Gastrointestinal"),
    ("Pantoprazole", "Pantoprazole", "40 mg", "Tablet", "Gastrointestinal"),
    ("ORS", "Oral rehydration salts", "WHO formula", "Powder sachet", "Rehydration"),
    ("Vitamin C", "Ascorbic acid", "500 mg", "Tablet", "Vitamin"),
    ("Vitamin D3", "Cholecalciferol", "1000 IU", "Tablet", "Vitamin"),
    ("Calcium", "Calcium carbonate", "500 mg", "Tablet", "Mineral supplement"),
    ("Metformin", "Metformin", "500 mg", "Tablet", "Antidiabetic"),
    ("Amlodipine", "Amlodipine", "5 mg", "Tablet", "Cardiovascular"),
    ("Losartan", "Losartan", "50 mg", "Tablet", "Cardiovascular"),
    ("Atorvastatin", "Atorvastatin", "10 mg", "Tablet", "Lipid-lowering"),
    ("Azithromycin", "Azithromycin", "500 mg", "Tablet", "Antibiotic"),
    ("Amoxicillin", "Amoxicillin", "500 mg", "Capsule", "Antibiotic"),
    ("Cefixime", "Cefixime", "200 mg", "Tablet", "Antibiotic"),
    ("Montelukast", "Montelukast", "10 mg", "Tablet", "Respiratory"),
    ("Salbutamol", "Salbutamol", "100 mcg", "Inhaler", "Respiratory"),
    ("Levocetirizine", "Levocetirizine", "5 mg", "Tablet", "Antihistamine"),
    ("Dextromethorphan", "Dextromethorphan", "10 mg/5 ml", "Syrup", "Cough preparation"),
    ("Diclofenac", "Diclofenac", "50 mg", "Tablet", "NSAID"),
    ("Clotrimazole", "Clotrimazole", "1%", "Cream", "Antifungal"),
    ("Mupirocin", "Mupirocin", "2%", "Ointment", "Topical antibiotic"),
]


def main() -> None:
    inserted = 0
    existing = 0
    with Session(engine) as session:
        for name, generic, strength, dosage_form, category in CATALOGUE:
            match = session.scalar(
                select(Medicine).where(
                    Medicine.name == name,
                    Medicine.strength == strength,
                    Medicine.dosageForm == dosage_form,
                ).limit(1)
            )
            if match:
                existing += 1
                continue
            session.add(
                Medicine(
                    name=name,
                    genericName=generic,
                    strength=strength,
                    dosageForm=dosage_form,
                    medicineCategory=category,
                    description="Generic catalogue entry for medicine return identification only.",
                )
            )
            inserted += 1
        session.commit()

    print(f"Catalogue entries defined: {len(CATALOGUE)}")
    print(f"Inserted: {inserted}")
    print(f"Already present (unchanged): {existing}")


if __name__ == "__main__":
    main()
