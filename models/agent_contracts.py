"""Pydantic modellen voor gestructureerde agent-output (Senior, Manager, Juniors).

Deze modellen worden gebruikt met ``llm.with_structured_output()`` om
fragiele regex-parsing en ongestructureerde vrije tekst te vervangen.
De Junior-combined modellen reduceren meerdere LLM-calls tot één per Junior.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from models.cdd_dossier import (
    IdentificatieVerificatie,
    IdentificatieVerificatieZakelijk,
    KlantprofielParticulier,
    KlantprofielZakelijk,
    Risicoclassificatie,
    Screening,
    ScreeningZakelijk,
    StructuurEnUbo,
)


class SeniorDecision(BaseModel):
    """Gestructureerde beslissing van de Senior Agent."""

    status: Literal["GOEDGEKEURD", "AFGEKEURD"] = Field(
        description="De eindstatus van de validatie: GOEDGEKEURD of AFGEKEURD.",
    )
    risicoclassificatie: Risicoclassificatie = Field(
        description=(
            "De risicoclassificatie van het dossier: Laag, Medium, "
            "Verhoogd of Onacceptabel."
        ),
    )
    onderbouwing_classificatie: str = Field(
        description=(
            "Korte toelichting waarom deze risicoclassificatie is toegekend, "
            "met verwijzing naar eventuele risicoverhogende factoren en hun "
            "mitigatie."
        ),
    )
    feedback_structuur: str | None = Field(
        default=None,
        description=(
            "Feedback specifiek voor Junior Structuur: wat ontbreekt of moet "
            "worden aangepast in identificatie, klantprofiel, screening of "
            "eigendomsstructuur. Laat leeg als er geen feedback is."
        ),
    )
    feedback_herkomst: str | None = Field(
        default=None,
        description=(
            "Feedback specifiek voor Junior Herkomst: wat ontbreekt of moet "
            "worden aangepast in de herkomst van middelen of HNWI-beoordeling. "
            "Laat leeg als er geen feedback is."
        ),
    )
    feedback_vermogen: str | None = Field(
        default=None,
        description=(
            "Feedback specifiek voor Junior Vermogen: wat ontbreekt of moet "
            "worden aangepast in het transactieprofiel, verwachte stortingen "
            "of verklaard vermogen. Laat leeg als er geen feedback is."
        ),
    )
    feedback_algemeen: str | None = Field(
        default=None,
        description=(
            "Overkoepelende feedback die meerdere juniors raakt of niet aan "
            "één junior toe te wijzen is (bijv. inconsistenties tussen secties). "
            "Laat leeg als er geen cross-cutting feedback is."
        ),
    )
    remaining_gaps: list[str] = Field(
        default_factory=list,
        description=(
            "Lijst van specifieke ontbrekende informatie of documenten die "
            "nog nodig zijn. Bij GOEDGEKEURD op de laatste iteratie: benoem "
            "hier de resterende gaps zodat het rapport deze als ONTBREKEND "
            "kan markeren. Laat leeg als er geen gaps zijn."
        ),
    )


class ManagerInstructions(BaseModel):
    """Gestructureerde instructies van de Manager Agent per Junior."""

    instructie_structuur: str = Field(
        description=(
            "Specifieke instructie voor Junior Structuur. Verwijs naar "
            "documenten met hun leesbare naam uit de Recon-index."
        ),
    )
    instructie_herkomst: str = Field(
        description=(
            "Specifieke instructie voor Junior Herkomst. Verwijs naar "
            "documenten met hun leesbare naam uit de Recon-index."
        ),
    )
    instructie_vermogen: str = Field(
        description=(
            "Specifieke instructie voor Junior Vermogen. Verwijs naar "
            "documenten met hun leesbare naam uit de Recon-index."
        ),
    )
    feedback_algemeen: str | None = Field(
        default=None,
        description=(
            "Algemene instructie of context die voor alle Juniors relevant is, "
            "bijvoorbeeld cross-cutting inconsistenties of een overkoepelende "
            "focus voor de volgende iteratie. Laat leeg als er geen algemene "
            "feedback is."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Combined Junior Structuur models (one LLM call instead of 3-4)
# ═══════════════════════════════════════════════════════════════════════════════

class JuniorStructuurParticulier(BaseModel):
    """Gecombineerde output van Junior Structuur voor particuliere klanten.

    Bevat alle secties die Junior Structuur in één keer invult, zodat de LLM
    alle context in één doorgang verwerkt en geen informatie verloren gaat.
    """

    identificatie_verificatie: IdentificatieVerificatie = Field(
        description="Identificatie en verificatie van de klant (par. 4.2.1-4.2.4).",
    )
    klantprofiel: KlantprofielParticulier = Field(
        description="Klantprofiel: arbeidsstatus, functie, sector, woonland, stromanconstructie.",
    )
    screening: Screening = Field(
        description="Screening tegen sanctielijsten, PEP-lijsten en adverse media (par. 4.3).",
    )


class JuniorStructuurZakelijk(BaseModel):
    """Gecombineerde output van Junior Structuur voor zakelijke klanten.

    Bevat alle secties die Junior Structuur in één keer invult, inclusief
    de eigendomsstructuur en UBO-informatie.
    """

    identificatie_verificatie: IdentificatieVerificatieZakelijk = Field(
        description=(
            "Identificatie en verificatie van de zakelijke klant en "
            "vertegenwoordiger(s) (par. 4.2.1-4.2.4)."
        ),
    )
    klantprofiel: KlantprofielZakelijk = Field(
        description="Klantprofiel: sector(en) en stromanconstructie.",
    )
    screening: ScreeningZakelijk = Field(
        description=(
            "Screening van zakelijke klant, tussenliggende entiteiten, "
            "vertegenwoordiger(s) en UBO('s) (par. 4.3)."
        ),
    )
    structuur_en_ubo: StructuurEnUbo = Field(
        description=(
            "Structuur & identificatie en verificatie UBO('s) "
            "(par. 4.2.5, 4.2.6, 4.4.6)."
        ),
    )
