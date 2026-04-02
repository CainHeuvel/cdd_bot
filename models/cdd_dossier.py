"""Pydantic modellen voor gestructureerde CDD-dossiers conform het CDD werkbestand v2.04.

Elke sectie is een onafhankelijk instantieerbaar model dat door een LangGraph-agent
via ``llm.with_structured_output(SectieModel)`` kan worden gegenereerd.  De top-level
dossiermodellen assembleren deze secties tot een compleet CDD-rapport.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Literals  (afgeleid van het "Drop down"-tabblad in het werkbestand)
# ═══════════════════════════════════════════════════════════════════════════════

Risicoclassificatie = Literal["Laag", "Medium", "Hoog", "Onacceptabel"]


# ═══════════════════════════════════════════════════════════════════════════════
# Atomaire bouwsteen
# ═══════════════════════════════════════════════════════════════════════════════

class WerkbladVraag(BaseModel):
    """Eén vraag-antwoord-rij uit het CDD-werkbestand.

    Spiegelt de kolommen: Antwoord | Toelichting | Geconstateerd risico |
    Verscherpt onderzoek en mitigatie | Risico-classificatie.

    Alleen ``antwoord`` is verplicht.  De overige velden hoeven alleen ingevuld
    te worden wanneer er een risicoverhogende factor is geïdentificeerd.
    """

    antwoord: str = Field(
        description="Het antwoord op de vraag uit het werkbestand.",
    )
    toelichting: str | None = Field(
        default=None,
        description=(
            "Aanvullende toelichting bij het antwoord.  Gebruik dit veld om de "
            "onderbouwing, context of verwijzingen naar brondocumenten te geven."
        ),
    )
    geconstateerd_risico: str | None = Field(
        default=None,
        description=(
            "Beschrijving van het geconstateerde risico, indien van toepassing.  "
            "Laat leeg als er geen risicoverhogende factor is geïdentificeerd."
        ),
    )
    verscherpt_onderzoek: str | None = Field(
        default=None,
        description=(
            "Beschrijving van het uitgevoerde verscherpt onderzoek en de "
            "mitigerende maatregelen.  Alleen invullen als er een verhoogd "
            "risico is geconstateerd."
        ),
    )
    risicoclassificatie: Risicoclassificatie | None = Field(
        default=None,
        description=(
            "Risicoclassificatie voor deze specifieke vraag: Laag, Medium, "
            "Hoog of Onacceptabel.  Laat leeg als er geen risicoverhogende "
            "factor is geïdentificeerd."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata
# ═══════════════════════════════════════════════════════════════════════════════

class DossierMetadata(BaseModel):
    """Header-informatie bovenaan elk CDD-dossier."""

    naam_client: str = Field(
        description="Volledige naam van de cliënt (rekeninghouder).",
    )
    naam_medewerker: str = Field(
        description="Naam van de CDD-analist die het dossier opstelt.",
    )
    naam_medewerker_vier_ogen: str | None = Field(
        default=None,
        description="Naam van de medewerker die de 4-ogencontrole uitvoert.",
    )
    datum: str = Field(
        description="Datum van het dossier in DD-MM-YYYY formaat.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Gedeelde secties  (gebruikt door meerdere klanttypes)
# ═══════════════════════════════════════════════════════════════════════════════

class IdentificatieVerificatie(BaseModel):
    """Sectie: Identificatie en verificatie van een natuurlijk persoon.

    Van toepassing op: Particulier, elke rekeninghouder bij Gezamenlijk,
    en de rekeninghouder bij Vertegenwoordiging (par. 4.2.1-4.2.4 Wwft-beleid).
    """

    verificatie_document: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt ter verificatie van de identiteit van "
            "de klant?  Verwachte antwoorden: Paspoort, Identiteitsbewijs.  "
            "Vermeld in toelichting het documentnummer en de geldigheidsdatum."
        ),
    )
    verificatie_methode: WerkbladVraag = Field(
        description=(
            "Hoe hebben we de identiteit van de klant geverifieerd?  "
            "Verwachte antwoorden: Fysieke afspraak, Facescan, iDIN."
        ),
    )


class Screening(BaseModel):
    """Sectie: Screening tegen sanctielijsten, PEP-lijsten en adverse media.

    Van toepassing op: Particulier, elke rekeninghouder/vertegenwoordiger
    bij Gezamenlijk en Vertegenwoordiging (par. 4.3 Wwft-beleid).
    """

    screening_resultaat: WerkbladVraag = Field(
        description=(
            "Wat komt er uit de screening van de klant tegen sanctielijsten, "
            "PEP-lijsten en adverse media?  Verwachte antwoorden: Geen hits, "
            "False positive, True positive.  Bij True positive: beschrijf de "
            "hit en de ondernomen acties in toelichting.  Bij PEP: vermeld de "
            "exacte functie en het land."
        ),
    )


class Leveringskanaalrisico(BaseModel):
    """Sectie: Leveringskanaalrisico.

    Gedeeld door alle vier klanttypes.
    """

    hoe_bij_bloei: WerkbladVraag = Field(
        description=(
            "Hoe is de klant bij Bloei terechtgekomen?  Verwachte antwoorden: "
            "Internet, Vergelijkingssite, Via bekenden, Intermediair, Anders.  "
            "Bij 'Anders' of 'Intermediair': specificeer in toelichting."
        ),
    )
    direct_contact: WerkbladVraag = Field(
        description=(
            "Heeft Bloei vermogen direct contact met de (wettelijke "
            "vertegenwoordiger(s) van de) klant?  Antwoord: Ja of Nee.  "
            "Indien Nee: licht toe waarom niet en welk risico dit oplevert."
        ),
    )


class DoelEnAard(BaseModel):
    """Sectie: Doel en aard van de relatie (par. 4.2.7 Wwft-beleid).

    Gedeeld door alle vier klanttypes.
    """

    doel_rekening: WerkbladVraag = Field(
        description=(
            "Wat is het doel van de klant bij het openen van een rekening bij "
            "Bloei vermogen?  Standaard: 'Beleggen van vermogen'.  Bij "
            "afwijkend doel: beschrijf in toelichting en beoordeel of dit past "
            "binnen de dienstverlening van Bloei."
        ),
    )
    doel_aard_passend: WerkbladVraag = Field(
        description=(
            "Is het doel en de aard van de relatie logisch en passend bij het "
            "klantprofiel en de dienstverlening van Bloei vermogen?  "
            "Antwoord: Ja of Nee.  Licht dit in een paar zinnen toe met "
            "verwijzing naar het klantprofiel, de herkomst van middelen en de "
            "verwachte transacties."
        ),
    )


class KlantprofielParticulier(BaseModel):
    """Sectie: Klantprofiel voor een natuurlijk persoon (par. 4.2 Wwft-beleid).

    Van toepassing op: Particulier, elke rekeninghouder bij Gezamenlijk,
    en de rekeninghouder bij Vertegenwoordiging.
    """

    arbeidsstatus: WerkbladVraag = Field(
        description=(
            "Wat is de huidige arbeidsstatus van de klant?  Verwachte "
            "antwoorden: Werknemer in loondienst, Zelfstandig ondernemer, "
            "Gepensioneerd, Politiek mandaat, Student, Geen werk."
        ),
    )
    functie: WerkbladVraag = Field(
        description=(
            "Welke functie bekleedt de klant?  N.v.t. bij gepensioneerd, "
            "student en geen werk.  Bij zelfstandig ondernemer: beschrijf de "
            "aard van de onderneming."
        ),
    )
    sector: WerkbladVraag = Field(
        description=(
            "In welke sector is de klant actief?  Beoordeel tegen Bijlage 3 "
            "(hoog-risicosectoren) van het Wwft-beleid.  Voorbeelden van "
            "hoog-risicosectoren: autohandel, bouwsector, cash-intensieve "
            "retail, vastgoedexploitatie, crypto/virtuele valuta, "
            "kunsthandel, wapenhandel.  Bij een hoog-risicosector: vermeld "
            "dit als geconstateerd risico."
        ),
    )
    woonland: WerkbladVraag = Field(
        description=(
            "In welk land woont de klant?  Beoordeel tegen Bijlage 2 "
            "(hoog-risicolanden: AFM-lijst, Art 9 AMLD4, FATF gray/black "
            "list) van het Wwft-beleid.  Bij een hoog-risicoland: vermeld "
            "dit als geconstateerd risico en beschrijf de binding met "
            "Nederland."
        ),
    )
    stromanconstructie: WerkbladVraag = Field(
        description=(
            "Is er reden om aan te nemen dat de klant mogelijk namens een "
            "derde optreedt (stromanconstructie)?  Antwoord: Ja of Nee.  "
            "Bij Ja: beschrijf de signalen en het risico."
        ),
    )


class HerkomstMiddelen(BaseModel):
    """Sectie: Herkomst van middelen & herkomst van vermogen.

    Par. 4.4.2, 5.1 Wwft-beleid + Bijlage 1.  Gedeeld door alle vier
    klanttypes.
    """

    herkomst_middelen: WerkbladVraag = Field(
        description=(
            "Wat is de herkomst van de middelen (= te beleggen vermogen)?  "
            "Selecteer alle toepasselijke bronnen.\n\n"
            "Particulier (10 bronnen conform Bijlage 1): Inkomen uit werk, "
            "Inkomen uit eigen onderneming, Inkomen uit pensioen, Verkoop "
            "vastgoed, Verkoop bedrijf, Winstuitkering of dividenduitkering, "
            "Erfenis, Schenking, Winst uit beleggen, Overig.\n\n"
            "Zakelijk (7 bronnen conform Bijlage 1): Inkomen uit eigen "
            "onderneming, Verkoop bedrijf, Winstuitkering of "
            "dividenduitkering, Agio storting, Verkoop vastgoed, Winst uit "
            "beleggen, Overig.\n\n"
            "Invullen bij antwoord: de geselecteerde bron(nen).\n"
            "Invullen bij toelichting: onderbouwing met de vragen uit "
            "Bijlage 1 (per bron de relevante vragen beantwoorden).\n"
            "Invullen bij verscherpt onderzoek: welke informatie/"
            "documentatie is gebruikt om dit vast te stellen (risk-based "
            "benadering).  Vermeld welke documenten aanwezig zijn en welke "
            "ONTBREKEN."
        ),
    )
    hnwi_status: WerkbladVraag = Field(
        description=(
            "Is er aanleiding om aan te nemen dat de klant een HNWI betreft?  "
            "HNWI-drempel: vrij beschikbaar vermogen > EUR 2.500.000 "
            "(par. 4.4.3 Wwft-beleid).\n\n"
            "Antwoord: Ja of Nee.\n\n"
            "Invullen bij toelichting: leg vast wat het (indicatief) totale "
            "vrij beschikbare vermogen van de klant is.  Bij Gezamenlijk: "
            "verdeel het vermogen over beide rekeninghouders.  Bij Zakelijk: "
            "bepaal HNWI-status per UBO apart en verdeel over alle UBO's.\n\n"
            "Indien HNWI: breng de verschillende componenten uit het totale "
            "vermogen in kaart (vastgoed, liquide middelen, beleggingen, "
            "pensioen, bedrijfswaarde, etc.) en beschrijf de verscherpte "
            "onderzoeksplicht."
        ),
    )
    herkomst_vermogen_overig: WerkbladVraag = Field(
        description=(
            "Is er een andere reden om onderzoek te doen naar de herkomst "
            "van het vermogen?  Antwoord: Ja of Nee.  Denk aan signalen uit "
            "transactiemonitoring, adverse media, mismatch tussen profiel en "
            "inleg, of andere risicoverhogende factoren.  Bij Ja: beschrijf "
            "de reden en het uitgevoerde onderzoek."
        ),
    )


class Transactieprofiel(BaseModel):
    """Sectie: Transactieprofiel.

    Gedeeld door alle vier klanttypes.
    """

    afwijkingen_vorig_onderzoek: WerkbladVraag = Field(
        description=(
            "(Bij periodieke review/remediation) Zijn er afwijkingen "
            "geconstateerd in het transactieprofiel ten opzichte van het "
            "vorige CDD-onderzoek?  Antwoord: Ja, Nee of N.v.t. (bij eerste "
            "onderzoek).  Bij Ja: beschrijf de afwijkingen in toelichting."
        ),
    )
    verwachte_stortingen: WerkbladVraag = Field(
        description=(
            "Wat verwacht de klant in het komende jaar te doen qua "
            "stortingen?  Invullen bij antwoord: het verwachte bedrag.  "
            "Invullen bij toelichting: context en onderbouwing."
        ),
    )
    verwachte_opnames: WerkbladVraag = Field(
        description=(
            "Wat verwacht de klant in het komende jaar te doen qua opnames?  "
            "Invullen bij antwoord: het verwachte bedrag.  "
            "Invullen bij toelichting: context en onderbouwing."
        ),
    )
    verklaard_vermogen: WerkbladVraag = Field(
        description=(
            "Wat is het verklaard vermogen van de klant voor het komende "
            "jaar?  Invullen bij antwoord: het verwachte bedrag.  Invullen "
            "bij toelichting: context en onderbouwing (baseer op inkomen, "
            "verwachte stortingen, bekende mutaties)."
        ),
    )
    transactieprofiel_type: WerkbladVraag = Field(
        description=(
            "Welk transactieprofiel krijgt de cliënt toegewezen en wat is "
            "hiervoor de onderbouwing?  Verwachte antwoorden: Harde VTP, "
            "Softe VTP, Doorlopende VTP.  Onderbouw de keuze in toelichting."
        ),
    )


class OverigeRisicos(BaseModel):
    """Sectie: Overige risico's.

    Gedeeld door alle vier klanttypes.  Vangnet voor risico's die niet in
    eerdere secties zijn benoemd.
    """

    overige_risicos: WerkbladVraag = Field(
        description=(
            "Zijn er nog overige risico's geconstateerd die niet in eerdere "
            "secties zijn benoemd?  Antwoord: Ja of Nee.  Bij Ja: beschrijf "
            "het risico in toelichting en geef aan welk verscherpt onderzoek "
            "is uitgevoerd."
        ),
    )


class Conclusie(BaseModel):
    """Sectie: Conclusie van het CDD-dossier.

    Gedeeld door alle vier klanttypes.
    """

    definitieve_risicoclassificatie: Risicoclassificatie = Field(
        description=(
            "De definitieve risicoclassificatie van het dossier: Laag, "
            "Medium, Hoog of Onacceptabel.  Gebaseerd op de hoogste "
            "individuele risicoclassificatie over alle secties, conform "
            "hoofdstuk 6 van het Wwft-beleid."
        ),
    )
    conclusie_dossier: str = Field(
        description=(
            "De samenvatting/conclusie van het CDD-dossier.  Bevat de "
            "definitieve beoordeling van het klantrisico, de belangrijkste "
            "bevindingen en eventuele aandachtspunten voor de toekomst."
        ),
    )
    toelichting_risicoclassificatie: str | None = Field(
        default=None,
        description=(
            "Korte toelichting bij de risicoclassificatie.  Verplicht bij "
            "Medium, Hoog of Onacceptabel.  Beschrijf de risicoverhogende "
            "factoren en de genomen mitigerende maatregelen."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Zakelijk-specifieke secties
# ═══════════════════════════════════════════════════════════════════════════════

class IdentificatieVerificatieZakelijk(BaseModel):
    """Sectie: Identificatie en verificatie van zakelijke klant en vertegenwoordiger(s).

    Par. 4.2.1-4.2.4 Wwft-beleid.  Alleen voor klanttype Zakelijk.
    """

    identificatie_zakelijk: WerkbladVraag = Field(
        description=(
            "Hoe is de zakelijke klant geïdentificeerd?  Verwacht antwoord: "
            "KvK-uittreksel.  Vermeld in toelichting het KvK-nummer, de "
            "rechtsvorm en de datum van het uittreksel."
        ),
    )
    identificatie_vertegenwoordigers: WerkbladVraag = Field(
        description=(
            "Hoe is/zijn de vertegenwoordiger(s) geïdentificeerd?  Verwacht "
            "antwoord: KvK-uittreksel.  Vermeld in toelichting de namen van "
            "de vertegenwoordigers en hun functie (bijv. bestuurder, "
            "gevolmachtigde)."
        ),
    )
    verificatie_document_vertegenwoordiger: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt ter verificatie van de identiteit van "
            "de vertegenwoordiger(s)?  Alleen van toepassing bij de "
            "vertegenwoordiger met wie wij contact hebben.  Verwachte "
            "antwoorden: Paspoort, Identiteitsbewijs."
        ),
    )
    verificatie_methode_vertegenwoordiger: WerkbladVraag = Field(
        description=(
            "Hoe hebben we de identiteit van de vertegenwoordiger(s) "
            "geverifieerd?  Alleen van toepassing bij de vertegenwoordiger "
            "met wie wij contact hebben.  Verwachte antwoorden: Fysieke "
            "afspraak, Facescan, iDIN."
        ),
    )


class StructuurEnUbo(BaseModel):
    """Sectie: Structuur & identificatie en verificatie UBO('s).

    Par. 4.2.5, 4.2.6, 4.4.6 Wwft-beleid.  Alleen voor klanttype Zakelijk.
    """

    eigendomsstructuur: WerkbladVraag = Field(
        description=(
            "Bespreek de eigendoms- en zeggenschapsstructuur van de zakelijke "
            "klant.  Invullen bij antwoord: beschrijving van de structuur.  "
            "Invullen bij toelichting: verwijzing naar relevante "
            "informatiebronnen (KvK-uittreksel, aandeelhoudersregister, "
            "statuten).  Vermeld alle tussenliggende entiteiten en hun "
            "aandelenpercentages.  Indien van toepassing: licht toe aan de "
            "hand van een (zelfgemaakt) organogram."
        ),
    )
    ubo_identificatie: WerkbladVraag = Field(
        description=(
            "Hoe is/zijn de UBO('s) geïdentificeerd?  Verwachte antwoorden: "
            "KvK-uittreksel, Aandeelhoudersregister, Statuten, Anders.  "
            "UBO = persoon met >25%% aandelen/stemrechten/eigendomsbelang "
            "(par. 4.2.6 Wwft-beleid).  Pseudo-UBO als uiterste terugval."
        ),
    )
    ubo_verificatie_document: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt ter verificatie van de identiteit van "
            "de UBO('s)?  Verwachte antwoorden: Paspoort, Identiteitsbewijs.  "
            "Vermeld in toelichting de namen van alle UBO's en hun "
            "aandelenpercentage."
        ),
    )
    ubo_register_match: WerkbladVraag = Field(
        description=(
            "Komt de UBO-bepaling overeen met de info uit het UBO-register?  "
            "Antwoord: Ja of Nee.  Bij Nee: beschrijf de discrepantie in "
            "toelichting en vermeld welke stappen zijn ondernomen."
        ),
    )
    complexe_structuur: WerkbladVraag = Field(
        description=(
            "Zit de zakelijke klant in een complexe structuur?  Antwoord: "
            "Ja of Nee.  Complex = >3 verticale lagen excl. natuurlijke "
            "personen, of aanwezigheid van StAK, Stichting, NV, FGR of NGO "
            "(par. 4.4.6 Wwft-beleid).  Onacceptabel: offshore entiteiten, "
            "Anglo-Saksische trusts, SPF, SPV, bearer shares, nominee "
            "shareholders.  Bij complexe structuur: beschrijf de structuur "
            "en het risico."
        ),
    )
    complexe_entiteit: WerkbladVraag = Field(
        description=(
            "Is de zakelijke klant gelinkt aan een complexe entiteit (die "
            "tussen de zakelijke klant en UBO in zit) en/of is de zakelijke "
            "klant zelf een complexe entiteit?  Antwoord: Ja of Nee.  "
            "Bij Ja: beschrijf welke entiteit en waarom deze als complex "
            "wordt beschouwd."
        ),
    )


class ScreeningZakelijk(BaseModel):
    """Sectie: Screening voor zakelijke klanten (par. 4.3 Wwft-beleid).

    Vier aparte screenings.  Alleen voor klanttype Zakelijk.
    """

    screening_zakelijke_klant: WerkbladVraag = Field(
        description=(
            "Wat komt er uit de screening van de zakelijke klant tegen "
            "sanctielijsten en adverse media?  Verwachte antwoorden: Geen "
            "hits, False positive, True positive.  Bij True positive: "
            "beschrijf de hit en de ondernomen acties."
        ),
    )
    screening_tussenliggende_entiteiten: WerkbladVraag = Field(
        description=(
            "Wat komt er uit de screening van de entiteit(en) tussen de "
            "zakelijke klant en de UBO's tegen sanctielijsten en adverse "
            "media?  N.v.t. indien geen tussenliggende entiteiten.  "
            "Verwachte antwoorden: Geen hits, False positive, True positive, "
            "N.v.t."
        ),
    )
    screening_vertegenwoordigers: WerkbladVraag = Field(
        description=(
            "Wat komt er uit de screening van de vertegenwoordiger(s) tegen "
            "sanctielijsten, PEP-lijsten en adverse media?  Verwachte "
            "antwoorden: Geen hits, False positive, True positive."
        ),
    )
    screening_ubos: WerkbladVraag = Field(
        description=(
            "Wat komt er uit de screening van de UBO('s) tegen "
            "sanctielijsten, PEP-lijsten en adverse media?  Verwachte "
            "antwoorden: Geen hits, False positive, True positive.  Bij PEP: "
            "vermeld de exacte functie en het land."
        ),
    )


class KlantprofielZakelijk(BaseModel):
    """Sectie: Klantprofiel voor zakelijke klanten.

    Alleen voor klanttype Zakelijk.
    """

    sector: WerkbladVraag = Field(
        description=(
            "In welke sector(en) is de zakelijke klant (indirect) actief?  "
            "Neem hierin ook de mogelijke werkmaatschappij/deelneming mee "
            "waar het geld vandaan komt.  Beoordeel tegen Bijlage 3 "
            "(hoog-risicosectoren) van het Wwft-beleid."
        ),
    )
    stromanconstructie: WerkbladVraag = Field(
        description=(
            "Is er reden om aan te nemen dat de zakelijke klant mogelijk "
            "namens een derde optreedt (stromanconstructie)?  Antwoord: Ja "
            "of Nee.  Bij Ja: beschrijf de signalen."
        ),
    )


class GeografischRisico(BaseModel):
    """Sectie: Geografisch risico (Bijlage 2 Wwft-beleid).

    Alleen voor klanttype Zakelijk.
    """

    vestigingsland: WerkbladVraag = Field(
        description=(
            "In welke land(en) is de zakelijke klant gevestigd?  Indien "
            "buitenland: wat is de binding met Nederland en waarom is de "
            "klant bij Bloei?  Beoordeel tegen Bijlage 2 (hoog-risicolanden)."
        ),
    )
    activiteitenland: WerkbladVraag = Field(
        description=(
            "In welke land(en) is de zakelijke klant (indirect) actief?  "
            "Indien buitenland: wat is de binding met Nederland en waarom "
            "is de klant bij Bloei?  Beoordeel tegen Bijlage 2."
        ),
    )
    ubo_woonland: WerkbladVraag = Field(
        description=(
            "In welk(e) land(en) is/zijn de UBO's woonachtig?  Indien "
            "buitenland: wat is de binding met Nederland en waarom is de "
            "klant bij Bloei?  Beoordeel tegen Bijlage 2 (hoog-risicolanden: "
            "AFM-lijst, Art 9 AMLD4, FATF gray/black list)."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Vertegenwoordiging-specifieke secties
# ═══════════════════════════════════════════════════════════════════════════════

class IdentificatieRekeninghouderVerteg(BaseModel):
    """Sectie: Identificatie en verificatie van de rekeninghouder bij vertegenwoordiging.

    Alleen voor klanttype Vertegenwoordiging.
    """

    verificatie_document: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt ter verificatie van de identiteit van "
            "de klant (rekeninghouder)?  Verwachte antwoorden: Paspoort, "
            "Identiteitsbewijs."
        ),
    )
    link_vertegenwoordiging: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt om de relatie tussen de "
            "rekeninghouder en de vertegenwoordiger(s) te onderbouwen?  "
            "Verwachte antwoorden: Geboorteakte, Screenshot MijnOverheid, "
            "Ockto, Anders.  Vermeld in toelichting de aard van de relatie "
            "(bijv. ouder-kind, bewindvoerder, curator, mentor)."
        ),
    )


class IdentificatieVertegenwoordiger(BaseModel):
    """Sectie: Identificatie en verificatie van een vertegenwoordiger.

    Alleen voor klanttype Vertegenwoordiging.
    """

    verificatie_document: WerkbladVraag = Field(
        description=(
            "Welk document is gebruikt ter verificatie van de identiteit van "
            "de vertegenwoordiger?  Verwachte antwoorden: Paspoort, "
            "Identiteitsbewijs."
        ),
    )
    verificatie_methode: WerkbladVraag = Field(
        description=(
            "Hoe hebben we de identiteit van de vertegenwoordiger "
            "geverifieerd?  Verwachte antwoorden: Fysieke afspraak, "
            "Facescan, iDIN."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Top-level dossiermodellen
# ═══════════════════════════════════════════════════════════════════════════════

class BaseCddDossier(BaseModel):
    """Basismodel met secties die door alle vier klanttypes worden gedeeld.

    Niet direct instantiëren — gebruik een van de concrete subklassen.
    """

    metadata: DossierMetadata = Field(
        description="Header-informatie: naam cliënt, analist, datum.",
    )
    leveringskanaalrisico: Leveringskanaalrisico = Field(
        description="Sectie leveringskanaalrisico: hoe is de klant bij Bloei terechtgekomen?",
    )
    doel_en_aard: DoelEnAard = Field(
        description="Sectie doel en aard van de relatie (par. 4.2.7 Wwft-beleid).",
    )
    herkomst_middelen: HerkomstMiddelen = Field(
        description=(
            "Sectie herkomst van middelen & herkomst van vermogen "
            "(par. 4.4.2, 5.1 Wwft-beleid + Bijlage 1)."
        ),
    )
    transactieprofiel: Transactieprofiel = Field(
        description="Sectie transactieprofiel: verwachte stortingen, opnames en verklaard vermogen.",
    )
    overige_risicos: OverigeRisicos = Field(
        description="Sectie overige risico's: vangnet voor niet eerder benoemde risico's.",
    )
    conclusie: Conclusie = Field(
        description="Sectie conclusie: definitieve risicoclassificatie en dossierconclusie.",
    )


class ParticulierDossier(BaseCddDossier):
    """CDD-dossier voor een particuliere klant (natuurlijk persoon)."""

    client_type: Literal["particulier"] = "particulier"

    identificatie_verificatie: IdentificatieVerificatie = Field(
        description="Identificatie en verificatie van de klant (par. 4.2.1-4.2.4).",
    )
    screening: Screening = Field(
        description="Screening tegen sanctielijsten, PEP-lijsten en adverse media (par. 4.3).",
    )
    klantprofiel: KlantprofielParticulier = Field(
        description="Klantprofiel: arbeidsstatus, functie, sector, woonland, stromanconstructie.",
    )


class GezamenlijkDossier(BaseCddDossier):
    """CDD-dossier voor gezamenlijke rekeninghouders (2 natuurlijke personen)."""

    client_type: Literal["gezamenlijk"] = "gezamenlijk"

    rekeninghouder_1_naam: str = Field(
        description="Volledige naam van rekeninghouder 1.",
    )
    rekeninghouder_2_naam: str = Field(
        description="Volledige naam van rekeninghouder 2.",
    )

    # Rekeninghouder 1
    identificatie_verificatie_rh1: IdentificatieVerificatie = Field(
        description="Identificatie en verificatie van rekeninghouder 1.",
    )
    screening_rh1: Screening = Field(
        description="Screening van rekeninghouder 1 tegen sanctielijsten, PEP-lijsten en adverse media.",
    )
    klantprofiel_rh1: KlantprofielParticulier = Field(
        description="Klantprofiel van rekeninghouder 1.",
    )

    # Rekeninghouder 2
    identificatie_verificatie_rh2: IdentificatieVerificatie = Field(
        description="Identificatie en verificatie van rekeninghouder 2.",
    )
    screening_rh2: Screening = Field(
        description="Screening van rekeninghouder 2 tegen sanctielijsten, PEP-lijsten en adverse media.",
    )
    klantprofiel_rh2: KlantprofielParticulier = Field(
        description="Klantprofiel van rekeninghouder 2.",
    )


class ZakelijkDossier(BaseCddDossier):
    """CDD-dossier voor een zakelijke klant (rechtspersoon)."""

    client_type: Literal["zakelijk"] = "zakelijk"

    naam_ubos_en_vertegenwoordigers: str = Field(
        description=(
            "Namen van de UBO('s) en vertegenwoordiger(s), gescheiden door "
            "komma's."
        ),
    )

    identificatie_verificatie: IdentificatieVerificatieZakelijk = Field(
        description=(
            "Identificatie en verificatie van de zakelijke klant en "
            "vertegenwoordiger(s) (par. 4.2.1-4.2.4)."
        ),
    )
    structuur_en_ubo: StructuurEnUbo = Field(
        description=(
            "Structuur & identificatie en verificatie UBO('s) "
            "(par. 4.2.5, 4.2.6, 4.4.6)."
        ),
    )
    screening: ScreeningZakelijk = Field(
        description=(
            "Screening van zakelijke klant, tussenliggende entiteiten, "
            "vertegenwoordiger(s) en UBO('s) (par. 4.3)."
        ),
    )
    klantprofiel: KlantprofielZakelijk = Field(
        description="Klantprofiel: sector(en) en stromanconstructie.",
    )
    geografisch_risico: GeografischRisico = Field(
        description="Geografisch risico: vestigingsland, activiteitenland, UBO-woonland (Bijlage 2).",
    )


class VertegenwoordigingDossier(BaseCddDossier):
    """CDD-dossier voor vertegenwoordiging (iemand treedt op namens de rekeninghouder)."""

    client_type: Literal["vertegenwoordiging"] = "vertegenwoordiging"

    vertegenwoordiger_1_naam: str = Field(
        description="Volledige naam van vertegenwoordiger 1.",
    )
    vertegenwoordiger_2_naam: str | None = Field(
        default=None,
        description="Volledige naam van vertegenwoordiger 2, indien van toepassing.",
    )

    # Rekeninghouder
    identificatie_rekeninghouder: IdentificatieRekeninghouderVerteg = Field(
        description=(
            "Identificatie en verificatie van de rekeninghouder, inclusief "
            "het document dat de relatie met de vertegenwoordiger(s) onderbouwt."
        ),
    )
    screening_rekeninghouder: Screening = Field(
        description="Screening van de rekeninghouder tegen sanctielijsten, PEP-lijsten en adverse media.",
    )
    klantprofiel: KlantprofielParticulier = Field(
        description="Klantprofiel van de rekeninghouder (niet de vertegenwoordiger).",
    )

    # Vertegenwoordiger 1
    identificatie_vertegenwoordiger_1: IdentificatieVertegenwoordiger = Field(
        description="Identificatie en verificatie van vertegenwoordiger 1.",
    )
    screening_vertegenwoordiger_1: Screening = Field(
        description="Screening van vertegenwoordiger 1 tegen sanctielijsten, PEP-lijsten en adverse media.",
    )

    # Vertegenwoordiger 2 (optioneel)
    identificatie_vertegenwoordiger_2: IdentificatieVertegenwoordiger | None = Field(
        default=None,
        description="Identificatie en verificatie van vertegenwoordiger 2, indien van toepassing.",
    )
    screening_vertegenwoordiger_2: Screening | None = Field(
        default=None,
        description="Screening van vertegenwoordiger 2, indien van toepassing.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Discriminated union
# ═══════════════════════════════════════════════════════════════════════════════

CddDossier = Union[
    ParticulierDossier,
    GezamenlijkDossier,
    ZakelijkDossier,
    VertegenwoordigingDossier,
]
"""Discriminated union van alle dossiertypen.  Dispatch op ``client_type``."""
