"""CDD-dossier Pydantic modellen.

Importeer de top-level dossiertypen of individuele secties voor gebruik met
``llm.with_structured_output()``.
"""

from models.cdd_dossier import (
    # Atomaire bouwsteen
    WerkbladVraag,
    # Metadata
    DossierMetadata,
    # Gedeelde secties
    Conclusie,
    DoelEnAard,
    HerkomstMiddelen,
    IdentificatieVerificatie,
    KlantprofielParticulier,
    Leveringskanaalrisico,
    OverigeRisicos,
    Screening,
    Transactieprofiel,
    # Zakelijk-specifieke secties
    GeografischRisico,
    IdentificatieVerificatieZakelijk,
    KlantprofielZakelijk,
    ScreeningZakelijk,
    StructuurEnUbo,
    # Vertegenwoordiging-specifieke secties
    IdentificatieRekeninghouderVerteg,
    IdentificatieVertegenwoordiger,
    # Top-level dossiers
    BaseCddDossier,
    GezamenlijkDossier,
    ParticulierDossier,
    VertegenwoordigingDossier,
    ZakelijkDossier,
    # Union type
    CddDossier,
    # Literal types
    Risicoclassificatie,
)

__all__ = [
    "WerkbladVraag",
    "DossierMetadata",
    "Conclusie",
    "DoelEnAard",
    "HerkomstMiddelen",
    "IdentificatieVerificatie",
    "KlantprofielParticulier",
    "Leveringskanaalrisico",
    "OverigeRisicos",
    "Screening",
    "Transactieprofiel",
    "GeografischRisico",
    "IdentificatieVerificatieZakelijk",
    "KlantprofielZakelijk",
    "ScreeningZakelijk",
    "StructuurEnUbo",
    "IdentificatieRekeninghouderVerteg",
    "IdentificatieVertegenwoordiger",
    "BaseCddDossier",
    "GezamenlijkDossier",
    "ParticulierDossier",
    "VertegenwoordigingDossier",
    "ZakelijkDossier",
    "CddDossier",
    "Risicoclassificatie",
]
