import streamlit as st


def projector_summary(lin=0):
    text_fin = """
    # Kaavoitusprojektori

    **_Kaavoitusprojektori_ on simulointimalli, joka on suunniteltu kaavoittajille ja kiinteistökehittäjille asuinrakentamisen luoman väestökehityksen ennustamiseen kaupunkisuunnittelukontekstissa. 
    Simulaatio muodostaa hankemitoitukseen pohjautuvia ennusteita ja auttaa visualisoimaan asuinrakentamisen typologioiden vaikutuksia väestökehitykseen. 
    Näin tehden se tarjoaa myös kokonaisvolyymejä tarkemman ja paikallisella asiantuntijuudella iteroitavan datan lukuisille monialaisille vaikutusarvioinneille.**

    ## Simulointimenetelmä

    Malli käyttää diskreettiä tapahtumasimulointimenetelmää [SimPy](https://simpy.readthedocs.io/en/latest/), 
    jolla erilaisten hankkeiden rakentaminen mallinnetaan tapahtumina ajassa niille asetettujen ominaispiirteiden mukaisesti
    kuvaten näin mahdollisimman todellista toteutumisvauhtia ja piirteiden tuottamaa väestöprofiilin kehitystä. 
    Simulaatio toimii päivätasolla, mutta tuottaa vuosittaiset tuotannon valmistumisennusteet ja niiden mukaisen väestöprofiilin 
    esiasetuksissa määritettyjen oletusten mukaisesti. Simuloinnin oletuksia säätämällä voidaan laatia hanke- ja sijaintikohtaisia 
    paikallistuntemukseen ja ajankohtaisiin näkemyksiin perustuvia skenaarioita ja vaihtoehtotarkasteluja.

    ## Rakennustyypit

    Malli tunnistaa kolme asuntorakennustyyppiä, joilla on erilliset ominaisuudet:

    **Omakotitalot/townhouse-talot**
    - Hankekoko: 100-200 m²
    - Rakentamisaika: noin 10 kuukautta
    - Korkeampi kapasiteettikerroin (4 x asetettu toteuttajien lukumäärä) kuvaten uudisalueen rakentamista pientalorakentajayhtiöiden ja hartiapankkirakentajien toimiessa saman aikaisesti

    **Rivitalot/paritalot/pienkerrostalot**
    - Hankekoko: 200-2,000 m²
    - Rakentamisaika: noin 12 kuukautta
    - Kohtalainen kapasiteettikerroin (2 x asetettu toteuttajien lukumäärä)

    **Kerrostalot**
    - Hankekoko: 2,000-9,000 m²
    - Rakentamisaika: noin 24 kuukautta
    - Peruskapasiteettikerroin (1x) vaativalle kerrostalotuotannolle

    Eriytetty kapasiteettiskaalaus kuvastaa sitä, että kevyemmissä rakennustyypeissä 
    toteutus jakautuu luontevammin useammille toimijoille.

    #### Hankkeen keston skaalautuminen

    Rakentamisaika mukautuu suhteellisesti hankkeen kokoon:

    **Todellinen kesto = Rakennustyypin perusrakentamisaika × (Hankkeen kerrosala / Tyypillinen kerrosala [vakioasetus])**

    Tämä varmistaa, että suuremmat hankkeet kestävät suhteellisesti pidempään, kun taas pienemmät hankkeet valmistuvat rakennustyypin keskiarvoa nopeammin.

    ## Asuntokoon ohjauskehys

    Kerrostalotuotannossa asuntojen kokojakaumaa ohjaavat määräykset ovat voimakkaita sääntelytyökaluja, 
    jotka vaikuttavat mm. asumisen hintaan, väestörakenteeseen ja seudulliseen kehitykseen. 
    
    #### Ohjauksen rakenne

    Projektori jakaa kerrostaloasunnot kolmeen kokoluokkaan:
    - **Pienet asunnot**: 20-40 m² (yksiöt ja pienet kaksiot)
    - **Keskikokoiset asunnot**: 40-70 m² (kaksiot ja kolmiot)
    - **Suuret asunnot**: 70-120 m² (suuremmat asunnot ja perheasunnot)

    Omakotitaloissa ei sovelleta kokoluokkajakoa, vaan ne sisältävät yhden asunnon, jonka koko on asetetun hankekoon mukainen.
    Rivi-, pari- ja pienkerrostaloissa sovelletaan kiinteää kokoluokkajakoa seuraavasti:  
    Asunnot ovat yli 70 m² (ei pienasuntoja), joista 30% on yli 100 m².

    Kerrostalojen ohjaus määritellään prosenttirajoituksina seuraavasti:
    - Enimmäisosuus asunnoista tietyn kokorajan alapuolella
    - Vähimmäisosuus asunnoista tietyn kokorajan yläpuolella

    **Esimerkki**: Ohjauspolitiikka, joka vaatii "enintään 50% alle 30 m²" ja "vähintään 20% yli 70 m²", 
    ohjaa väestökehitystä monipuolisempaan suuntaan, kuin pelkkä pientalovaltainen tuotanto.

    #### Asuntojen allokointi

    Rakennuksille muodostetaan huoneistoala tehokkuuskertoimen avulla. Kerrostalotuotannossa käytetään lisäasetuksissa määritettyä kerrointa ja muussa tuotannossa vakiokerrointa 0.8. 
    Huonestoala jaetaan pieniin, keskisuuriin ja suuriin asuntoihin ohjauspolitiikan mukaisesti. 
    Malli toteuttaa pieniä ja suuria asuntoja koskevat ehdot deterministisesti ja jakaa lopun huoneistoalan keskikokoisiin asuntoihin.
    Jos ohjausta ei aseteta, käytetään dynaamista baseline-jakaumaa, joka peilaa nykyaikaisia toteutumia Pohjoismaisessa rakentamisessa seuraavasti:  
    - pienet kerrostalot (<3000 m²) → tasapainoinen jakauma (1/3 kutakin kokoluokkaa)
    - keskikokoiset (3000 - 5000 m²) → asteittainen siirtymä kohti pienasuntovaltaisuutta
    - suuret kerrostalot (>5000 m²) → pienet asunnot dominoivat (75% pienet, 15% keskikokoiset, 10% suuret)

    ## Väestöennusteet

    Malli muuntaa toteutuneet asuntoyksiköt (huoneistot) väestöarvioiksi "asuttamalla" ne 
    asuntokoon mukaisesti lisäasetuksissa määritellyillä suhteilla, joiden esiasetetut arvot 
    ovat seuraavat:

    **Pienet asunnot (20-40 m²)**
    - Yhden hengen kotitaloudet: 90%
    - Muut kotitaloudet: 10%
    - Perhetaloudet: 0%

    **Keskikokoiset asunnot (40-70 m²)**
    - Yhden hengen kotitaloudet: 60%
    - Perhetaloudet: 20%
    - Muut kotitaloudet: 20%

    **Suuret asunnot (70-200 m²)**
    - Perhetaloudet: 90%
    - Yhden hengen kotitaloudet: 0%
    - Muut kotitaloudet: 10%

    Suhteita voi muuttaa lisäasetuksissa räätälöitäessä ennustetta kullekin hankkeelle.

    Väestökehitys lasketaan vuosittain valmistuneen tuotannon mukaan seuraavasti:

    **Kokonaisväestö = (Perheet × <perhekokoasetus>) + (Yksinasujat × 1,0) + (Muut × 2,0)**

    Nämä kertoimet kuvaavat:
    - Perhetaloudet: keskimäärin N henkilöä lisäasetuksissa määritetyn mukaan (lapsipariskunnat ja muut monen hengen taloudet)
    - Yhden hengen kotitaloudet: 1 henkilö
    - Muut kotitaloudet: keskimäärin 2 henkilöä (kimppakämpät, jaettu asuminen)

    ## Sovellukset kaavoituksessa

    #### Yleis/asemakaavoitus

    Työkalu tukee pitkän aikavälin suunnittelua:
    - Mallintamalla realistisia projektioita eri aikajänteillä
    - Auttamalla koordinoimaan infrastruktuurin toteutusta asuntojen valmistumisaikataulujen kanssa
    - Arvioimalla hankealoitusten ja niihin tulevien muutosten vaikutusta
    - Tuo esiin eri kaavamääräysten vaikutuksia väestörakenteen tasapainoon
    - Auttaa arvioimaan palvelutarpeita eri väestöryhmille (päivähoito, koulut, joukkoliikenne)
    - Luo perustellun ja sijaintiin räätälöidyn pohjadatan monialaisille vaikutusarvioinneille

    #### Vaikutusarvioinnit

    Mallinnus tuottaa tarkan hankekohtaisesti perustellun datan lukuisille vaikutusarvioinneille:
    - Suorat ja välilliset hiilijalanjälkiarviot (rakentaminen vs käyttö) ajan suhteen
    - viheralueiden kuormituksen arviointi
    - infrastruktuurin ja joukkoliikenteen kysyntäkehitys
    - palvelukysynnän kasvu (puistot, päiväkodit, koulut, terveydenhuolto, vähittäiskauppa jne.)
    - verotuloprojektiot
    - segregaation kehitys

    """

    text_eng = """
    # Zoning Projector

    **_Zoning Projector_ is a simulation model designed for urban planners and real estate developers to forecast population dynamics from residential construction within urban planning contexts.
    The simulation generates unit-based forecasts and helps visualize the impact of residential building typologies on population development.
    This provides detailed, locally-adaptive data for comprehensive multi-disciplinary impact assessments.**

    ## Simulation Method

    The model uses discrete event simulation via [SimPy](https://simpy.readthedocs.io/en/latest/),
    modeling various projects' construction as time-based events with assigned characteristics,
    reflecting realistic development pace and population profile evolution.
    Simulation operates at daily resolution while producing annual completion forecasts and corresponding population profiles
    based on predefined assumptions. Scenario variations and comparative analyses can be developed by adjusting simulation parameters
    to reflect project-specific and location-specific insights.

    ## Building Typologies

    The model recognizes three residential building types with distinct characteristics:

    **Single-family/townhouses**
    - Project size: 100-200 m²
    - Construction time: approximately 10 months
    - Higher capacity multiplier (4x developer count) reflecting development with multiple builders operating simultaneously

    **Row/semi-detached/low-rise apartments**
    - Project size: 200-2,000 m²
    - Construction time: approximately 12 months
    - Moderate capacity multiplier (2x developer count)

    **Apartment buildings**
    - Project size: 2,000-9,000 m²
    - Construction time: approximately 24 months
    - Base capacity multiplier (1x) for complex apartment development

    Differentiated capacity scaling reflects that lighter building types naturally distribute across multiple developers.

    #### Project Duration Scaling

    Construction time scales proportionally with project size:  
    **Actual duration = Building type base time × (Project floor area / Typical floor area [default])**  

    This ensures larger projects take proportionally longer, while smaller projects complete faster than the building type average.

    ## Housing Size Framework

    In apartment development, size distribution regulations are powerful planning tools
    affecting housing affordability, demographic composition, and regional development.

    #### Framework Structure

    The projector classifies apartment units into three size categories:
    - **Small units**: 20-40 m² (studios and small one-bedroom)
    - **Medium units**: 40-70 m² (one/two-bedroom)
    - **Large units**: 70-120 m² (larger units and family housing)

    Single-family homes apply no size classification—containing one unit sized according to project specifications.
    Row, semi-detached, and low-rise buildings use fixed distribution: All units exceed 70 m² with 30% exceeding 100 m².

    Apartment building regulations apply percentage constraints:
    - Maximum share of units below certain size threshold
    - Minimum share of units above certain size threshold

    **Example**: A regulation requiring "maximum 50% below 30 m²" and "minimum 20% above 70 m²"
    guides more balanced demographic development than pure small-unit-focused production.

    #### Unit Allocation

    Building floor area is established via efficiency multipliers. Apartments use settings-defined coefficients; other typologies use standard 0.8.
    Floor area distributes among small, medium, and large units per policy. The model implements small and large unit requirements deterministically,
    allocating remaining area to medium units. Without policy constraints, dynamic baseline distribution reflects contemporary Nordic practice:
    - Small projects (<3,000 m²) → balanced distribution (1/3 each category)
    - Medium (3,000-5,000 m²) → gradual shift toward small-unit emphasis
    - Large projects (>5,000 m²) → small units dominate (75% small, 15% medium, 10% large)

    ## Population Forecasts

    The model converts completed units into population estimates by "occupying" them
    using size-based household ratios with defaults:

    **Small units (20-40 m²)**
    - Single-person households: 90%
    - Other households: 10%
    - Family households: 0%

    **Medium units (40-70 m²)**
    - Single-person households: 60%
    - Family households: 20%
    - Other households: 20%

    **Large units (70-200 m²)**
    - Family households: 90%
    - Single-person households: 0%
    - Other households: 10%

    Ratios can be customized when refining forecasts for specific projects.

    Annual population growth calculation:  
    **Total population = (Families × <family size setting>) + (Singles × 1.0) + (Other × 2.0)**

    Coefficients represent:
    - Family households: average N persons per settings (couples with children, multi-person households)
    - Single-person households: 1 person
    - Other households: average 2 persons (shared living, co-housing)

    ## Planning Applications

    #### Master/detail planning

    The tool supports long-term planning:
    - Modeling realistic projections across timeframes
    - Coordinating infrastructure delivery with housing completion schedules
    - Assessing impacts of project initiation and modifications
    - Revealing regulatory effects on demographic balance
    - Estimating service demands for population segments (childcare, schools, transit)
    - Providing substantiated, location-adapted baseline data for multi-disciplinary assessments

    #### Impact Assessments

    Modeling produces precise, project-justified data for assessments:
    - Direct and indirect carbon footprint estimates (construction vs. operations) over time
    - Green space capacity assessment
    - Infrastructure and transit demand development
    - Service demand growth (parks, childcare, schools, healthcare, retail, etc.)
    - Tax revenue projections
    - Segregation dynamics
    """

    if lin == 0:
        text = text_fin
    else:
        text = text_eng
        
    return text
