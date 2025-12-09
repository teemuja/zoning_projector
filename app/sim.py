#coded in API-ready format..
import streamlit as st
import pandas as pd
import simpy
import numpy as np
import datetime
import uuid
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def main_sim(args):
    """
    Orchestrates:
      1) project-level construction timing (SimPy)
      2) unit-size allocation & population estimation

    Expected keys in args:
      - buildings: list of {type, gfa} dicts from conceptor()
      - pre_con_time: infra lead time (years)
      - construction_times: optional per-type durations (months)
      - num_companies: parallel construction capacity
      - unit_size_policy: {'apartment-condo': [pct_small_max, size1, pct_large_min, size2]} or None
      - household_shares_estimates: dict with 'small','medium','large','family_houses'
      - avg_family_size: numeric
      - apt_efficiency: apartment-condo efficiency (0.7 - 0.9 typically)
    """

    buildings_data = args.get("buildings", [])
    pre_con_time = int(args.get("pre_con_time", 2))
    construction_times = args.get("construction_times", None)
    num_companies = int(args.get("num_companies", 1))

    unit_size_policy = args.get("unit_size_policy", None)
    household_shares_estimates = args.get("household_shares_estimates", None)
    avg_family_size = float(args.get("avg_family_size", 3.5))
    apt_efficiency = float(args.get("apt_efficiency", 0.8))

    # 1) simulate construction timing
    constructed_buildings = construction(
        buildings_data,
        pre_con_time=pre_con_time,
        construction_times=construction_times,
        num_companies=num_companies,
    )

    # 2) allocate units & population
    sim_data = apply_unit_size_policy(
        constructed_buildings,
        household_shares=household_shares_estimates,
        policy=unit_size_policy,
        avg_family_size=avg_family_size,
        apt_efficiency=apt_efficiency,
    )

    return {"body": sim_data}



# -------- construction simpy -------

def construction(buildings, pre_con_time=2, construction_times=None, num_companies=1):
    """
    Deterministic construction simulation.

    Input:
      buildings: list of dicts with keys:
        - type: 'one-family-house', 'multi-family-house', 'apartment-condo', ...
        - gfa: total GFA for that project
    Output:
      list of dicts with:
        - project_id
        - con_year
        - volume (GFA)
        - type
        - company
    """

    # Default construction times in months
    if construction_times is None:
        construction_times = {
            "one-family-house":   {"constime": 10},
            "multi-family-house": {"constime": 12},
            "apartment-condo":    {"constime": 24},
        }

    env = simpy.Environment()
    DAYS_PER_YEAR = 365
    DAYS_PER_MONTH = 30

    # queue projects by type
    building_queues = {}
    for b in buildings:
        btype = b["type"]
        gfa = b["gfa"]
        if btype not in building_queues:
            building_queues[btype] = []
        building_queues[btype].append({
            "project_id": uuid.uuid4().hex,
            "type": btype,
            "gfa": gfa,
        })

    completed = []

    def worker(env, queue, building_type, base_constime, worker_id, typical_gfa):
        while queue:
            proj = queue.pop(0)
            gfa = proj["gfa"]

            if typical_gfa and typical_gfa > 0:
                months = base_constime * (gfa / typical_gfa)
            else:
                months = base_constime

            duration_days = int(max(1, months) * DAYS_PER_MONTH)
            yield env.timeout(duration_days)

            years_passed = env.now // DAYS_PER_YEAR
            completion_year = (
                datetime.datetime.now().year
                + int(pre_con_time)
                + int(years_passed)
            )

            completed.append({
                "project_id": proj["project_id"],
                "con_year": int(completion_year),
                "volume": gfa,
                "type": building_type,
                "company": worker_id,
            })

    # spawn workers per type
    for btype, queue in building_queues.items():
        base_constime = construction_times.get(btype, {}).get("constime", 12)
        gfa_values = [p["gfa"] for p in queue]
        typical_gfa = int(np.mean(gfa_values)) if gfa_values else None

        multiplier_map = {
            "apartment-condo":    1,
            "multi-family-house": 2,
            "one-family-house":   4,
        }
        mult = multiplier_map.get(btype, 1)
        worker_count = max(1, int(num_companies * mult))

        for worker_id in range(1, worker_count + 1):
            env.process(
                worker(env, queue, btype, base_constime, worker_id, typical_gfa)
            )

    env.run()

    # fill missing years with zero-volume dummy entries (for plotting continuity)
    if completed:
        start_year = datetime.datetime.now().year + int(pre_con_time)
        max_year = max(c["con_year"] for c in completed)
        all_years = range(start_year, max_year + 1)
        years_present = set(c["con_year"] for c in completed)

        for y in all_years:
            if y not in years_present:
                completed.append({
                    "project_id": None,
                    "con_year": y,
                    "volume": 0,
                    "type": "none",
                    "company": None,
                })

    completed.sort(key=lambda x: (x["con_year"], x["project_id"] or ""))

    return completed




# -------- units & households -------
def apply_unit_size_policy(
    buildings,
    household_shares=None,
    policy=None,
    avg_family_size=3.5,
    apt_efficiency=0.8   # user-defined efficiency for apartment-condos
):
    """
    Final version with:
      - dynamic baseline mix
      - deterministic unit allocation
      - GFA → net GFA using efficiency factors
      - per-building-type efficiencies:
           * one-family-house  = 0.80 (fixed)
           * multi-family-house = 0.80 (fixed)
           * apartment-condo    = apt_efficiency (user controlled)
    """

    # --- Default household distribution ---
    if household_shares is None:
        household_shares = {
            "small":  {"range": (20,40),  "distribution": [0,90,10]},
            "medium": {"range": (40,70),  "distribution": [20,60,20]},
            "large":  {"range": (70,120), "distribution": [90,0,10]},
            "family_houses": {"range": (100,200), "distribution": [95,0,5]}
        }

    # Helper: centroid of range
    def centroid(rng):
        return (rng[0] + rng[1]) / 2

    # --- Dynamic market baseline ---
    def dynamic_baseline_mix(gfa):
        small_low, medium_low, large_low = 0.30, 0.35, 0.35
        small_high, medium_high, large_high = 0.75, 0.15, 0.10

        gfa_min, gfa_max = 3000, 4500

        if gfa <= gfa_min:
            return small_low, medium_low, large_low
        if gfa >= gfa_max:
            return small_high, medium_high, large_high

        # interpolate
        t = (gfa - gfa_min) / (gfa_max - gfa_min)
        bs = small_low  + t * (small_high  - small_low)
        bm = medium_low + t * (medium_high - medium_low)
        bl = large_low  + t * (large_high  - large_low)
        return bs, bm, bl

    updated = []

    # =====================================================================
    #                         PROCESS EACH PROJECT
    # =====================================================================
    for b in buildings:

        btype = b["type"]
        gfa   = b["volume"]

        # -------------------------------------------------------
        # 1) BUILDING-TYPE SPECIFIC EFFICIENCY
        # -------------------------------------------------------
        if btype == "one-family-house":
            efficiency_factor = 0.80
        elif btype == "multi-family-house":
            efficiency_factor = 0.80
        elif btype == "apartment-condo":
            efficiency_factor = float(apt_efficiency)
        else:
            efficiency_factor = 0.80  # fallback

        # convert GFA → net floor area for units
        net_gfa = gfa * efficiency_factor

        out = b.copy()

        # -------------------------------------------------------
        # 2) ONE-FAMILY HOUSE — fixed logic (always 1 unit)
        # -------------------------------------------------------
        if btype == "one-family-house":
            out["small"] = 0
            out["medium"] = 0
            out["large"] = 1

            fh_f, fh_s, fh_o = household_shares["family_houses"]["distribution"]
            out["families"] = int(round((fh_f/100) * avg_family_size))
            out["singles"]  = int(round(fh_s/100))
            out["other"]    = int(round((fh_o/100) * 2))

            out["avg_unit_size"] = round(net_gfa / 1)
            updated.append(out)
            continue

        # -------------------------------------------------------
        # 3) MULTI-FAMILY HOUSE (semi-detached / rowhouses)
        # -------------------------------------------------------
        if btype == "multi-family-house":

            total_units = max(1, round(net_gfa / 90))  # larger unit sizes

            L = int(0.30 * total_units)
            M = total_units - L
            S = 0

            out["small"]  = S
            out["medium"] = M
            out["large"]  = L
            out["avg_unit_size"] = round(net_gfa / total_units)

            fh_f, fh_s, fh_o = household_shares["family_houses"]["distribution"]
            out["families"] = int(round(total_units * fh_f * avg_family_size / 100))
            out["singles"]  = int(round(total_units * fh_s / 100))
            out["other"]    = int(round(total_units * fh_o * 2 / 100))

            updated.append(out)
            continue

        # -------------------------------------------------------
        # 4) APARTMENT-CONDOS (main case, with policy)
        # -------------------------------------------------------

        # 4.1 Market baseline
        bs, bm, bl = dynamic_baseline_mix(net_gfa)

        # 4.2 Average sizes (centroids)
        s_avg = centroid(household_shares["small"]["range"])
        m_avg = centroid(household_shares["medium"]["range"])
        l_avg = centroid(household_shares["large"]["range"])

        # 4.3 Expected average unit size
        expected_unit_size = (
            bs * s_avg +
            bm * m_avg +
            bl * l_avg
        )
        expected_unit_size = max(20, expected_unit_size)

        # 4.4 Total units from net_gfa
        total_units = max(1, round(net_gfa / expected_unit_size))

        # 4.5 Policy (if enabled)
        if policy is None or "apartment-condo" not in policy:
            c = {
                "pct_small_max": 75,
                "size_small_max": s_avg,
                "pct_large_min": 10,
                "size_large_min": l_avg
            }
        else:
            pct1, size1, pct2, size2 = policy["apartment-condo"]
            c = {
                "pct_small_max": pct1,
                "size_small_max": size1,
                "pct_large_min": pct2,
                "size_large_min": size2
            }

        # 4.6 Baseline unit counts before constraints
        baseline_small  = int(bs * total_units)
        baseline_large  = int(bl * total_units)
        baseline_medium = total_units - baseline_small - baseline_large

        # 4.7 Apply constraints
        S = min(baseline_small, int(c["pct_small_max"] / 100 * total_units))
        L = max(baseline_large, int(c["pct_large_min"] / 100 * total_units))
        M = total_units - S - L

        if M < 0:
            raise ValueError("Policy impossible: S + L > total_units")

        out["small"] = S
        out["medium"] = M
        out["large"] = L
        out["avg_unit_size"] = round(net_gfa / total_units)

        # 4.8 Households (deterministic)
        s_f,s_s,s_o = household_shares["small"]["distribution"]
        m_f,m_s,m_o = household_shares["medium"]["distribution"]
        l_f,l_s,l_o = household_shares["large"]["distribution"]

        fam = (S*s_f/100 + M*m_f/100 + L*l_f/100) * avg_family_size
        sng = (S*s_s/100 + M*m_s/100 + L*l_s/100)
        oth = (S*s_o/100 + M*m_o/100 + L*l_o/100) * 2

        out["families"] = int(round(fam))
        out["singles"]  = int(round(sng))
        out["other"]    = int(round(oth))

        updated.append(out)

    return updated





# --------- conceptor ------------
def conceptor(lin=1):

    #LOCAT
    one_family_house_vol_title = ['Pientalojen kokonaismitoitus','One-family-house volume']
    multi_family_house_vol_title = ['Rivitalojen kokonaismitoitus','Multi-family-house volume']
    apartment_building_vol_title = ['Kerrostalojen kokonaismitoitus','Apartment building volume']
    one_family_house_pro_title = ['Pientalojen hankekoko','One-family-house project size']
    multi_family_house_pro_title = ['Rivitalojen hankekoko','Multi-family-house project size']
    apartment_building_pro_title = ['Kerrostalojen hankekoko','Apartment building project size']
    num_of_con_companies_title = ["Samanaikainen tuotanto","Paraller construction"]
    pre_con_and_sim_time_title = ['Esirakentamisaika','Pre-construction time']
    unit_size_policy_selection = ['Käytä asuntokoon ohjauspolitiikkaa','Apply unit size policy']

    #helps
    vol_help = ['Kokonaismitoitus ja hankekoko kerrosalaneliömetreissä (kem²)','Total volume and project size as Gross Floor Area square meters (GFAm²)']
    num_of_con_companies_help = ["Samanaikaisesti toteutuvien hakkeiden lukumäärä vuodessa",
                                "Number of parallel on-going implementation projects yearly"]
    pre_con_and_sim_time_help = ['Aseta infrastruktuurin esirakentamisaika',
                                'Set pre-construction time for infrastructure']

    basic_conceptor_title = ["Perusasetukset","Basic settings"]
    enh_conceptor_title = ["Lisäasetukset","Advanced settings"]

    # defaults
    step=1000
    one_family_default_volume = 5000
    multi_family_default_volume = 10000
    apartment_default_volume = 40000
    max_volume = 100000

    with st.expander(basic_conceptor_title[lin],expanded=True):
        s1,s2 = st.columns(2)    
        one_family_house_vol = s1.slider(one_family_house_vol_title[lin], 0, max_volume, one_family_default_volume, step=step, help=vol_help[lin])
        one_family_house_pro = s2.slider(one_family_house_pro_title[lin], 50, 200, 120, step=10)
        multi_family_house_vol = s1.slider(multi_family_house_vol_title[lin], 0, max_volume, multi_family_default_volume, step=step)
        multi_family_house_pro = s2.slider(multi_family_house_pro_title[lin], 200, 2000, 900, step=100)
        apartment_condo_vol = s1.slider(apartment_building_vol_title[lin], 0, max_volume, apartment_default_volume, step=step*5)
        apartment_condo_pro = s2.slider(apartment_building_pro_title[lin], 2000, 9000, 5000, step=1000)
        num_comp = s1.slider(num_of_con_companies_title[lin], 1, 5, 3, step=1,
                                help=num_of_con_companies_help[lin])
        # `pre_con_sim_time` is pre-construction time (years) for enabling roads, utilities etc.
        pre_con_sim_time = s2.slider(pre_con_and_sim_time_title[lin], 1, 9, 3, step=1,
                                        help=pre_con_and_sim_time_help[lin])

    with st.expander(enh_conceptor_title[lin],expanded=False):

        lang = "FIN" if lin==0 else "ENG"

        TITLE_TRANSLATIONS = {
            "size_range": {
                "FIN": "Kokohaarukka",
                "ENG": "Size range"
            },
            "families": {
                "FIN": "Perheet (%)",
                "ENG": "Families (%)"
            },
            "singles": {
                "FIN": "Sinkut (%)",
                "ENG": "Singles (%)"
            },
            "others": {
                "FIN": "Muut (%)",
                "ENG": "Other households (%)"
            },
            "small_apartments": {
                "FIN": "Pienet asunnot",
                "ENG": "Small apartments"
            },
            "medium_apartments": {
                "FIN": "Keskikokoiset asunnot",
                "ENG": "Medium apartments"
            },
            "large_apartments": {
                "FIN": "Isot asunnot",
                "ENG": "Large apartments"
            },
            "family_houses": {
                "FIN": "Omakotitalot",
                "ENG": "Family houses"
            }
        }

        def t(key: str, lang: str = "FIN") -> str:
            return TITLE_TRANSLATIONS.get(key, {}).get(lang, key)


        
        house_hold_shares_estimates_default = {
            "small_apartments": {"size_range": [20, 40], "distribution": [0, 90, 10]},
            "medium_apartments": {"size_range": [40, 70], "distribution": [20, 60, 20]},
            "large_apartments": {"size_range": [70, 120], "distribution": [90, 0, 10]},
            "family_houses": {"size_range": [100, 200], "distribution": [95, 0, 5]}
        }

        cols = st.columns(2)
        updated_values = {}

        for idx, (apt_type, vals) in enumerate(house_hold_shares_estimates_default.items()):
            
            col = cols[idx % 2]
            title = t(apt_type, lang)

            # Display default size range as static text (non-editable)
            smin, smax = vals["size_range"]
            col.write(f"{title} — {t('size_range', lang)}: **{smin} - {smax} m²**")

            dist = vals["distribution"]

            # Families slider
            families = col.slider(
                f"{title} — {t('families', lang)}",
                min_value=0, max_value=100,
                value=dist[0], step=5
            )

            # Singles slider
            max_singles = 100 - families
            singles = col.slider(
                f"{title} — {t('singles', lang)}",
                min_value=0, max_value=max_singles,
                value=min(dist[1], max_singles),
                step=5
            )

            # Automatically computed "others"
            others = 100 - families - singles

            # Show as label instead of slider
            col.write(f"{t('others', lang)}: **{others}%**")

            distribution = [families, singles, others]

            dist_sum = sum(distribution)

            if dist_sum > 100:
                col.error(f"{title}: {dist_sum}% > 100%")

            updated_values[apt_type] = {
                "size_range": [smin, smax],
                "distribution": [families, singles, others]
            }

        enh1, enh2 = st.columns(2)
        #avg_family_size
        avg_family_size_slider_text = ['Keskimääräinen perhekoko','Average family size']
        avg_family_size = enh1.slider(avg_family_size_slider_text[lin], 2.0, 6.0, 3.5, step=0.1)
        #apartment_efficiency_factor
        apartment_efficiency_factor_slider_text = ['Kerrostalotuotannon tehokkuuskerroin','Apartment efficiency factor']
        apartment_efficiency_factor = enh2.slider(apartment_efficiency_factor_slider_text[lin], 0.7, 0.9, 0.8, step=0.05,
                                                help=['Kerrostalojen kerrosalan muuntosuhde huoneistoneliömetreiksi, joiden perusteella laskenta tehdään.',
                                                      'Conversion factor from apartment buildings GFA to net residential floor area, based on which the calculation is made.'][lin])

        # ---- update values ----
        # Translate UI outputs into model-compatible household distribution structure
        house_hold_shares_estimates = {
            "small": {
                "range": updated_values["small_apartments"]["size_range"],
                "distribution": updated_values["small_apartments"]["distribution"],
            },
            "medium": {
                "range": updated_values["medium_apartments"]["size_range"],
                "distribution": updated_values["medium_apartments"]["distribution"],
            },
            "large": {
                "range": updated_values["large_apartments"]["size_range"],
                "distribution": updated_values["large_apartments"]["distribution"],
            },
            "family_houses": {
                "range": updated_values["family_houses"]["size_range"],
                "distribution": updated_values["family_houses"]["distribution"],
            },
        }

    # prepare building..

    #volumes out as dict
    total_gfa_volumes = {
        'one-family-house': one_family_house_vol,
        'multi-family-house': multi_family_house_vol,
        'apartment-condo': apartment_condo_vol
        }
    project_sizes = {
        'one-family-house': one_family_house_pro,
        'multi-family-house': multi_family_house_pro,
        'apartment-condo': apartment_condo_pro
        }
    

    # --- subfunc to gen projects from volumes ---
    def generate_projects(total_volumes: dict, project_sizes: dict):
        buildings = []

        for building_type, total_volume in total_volumes.items():
            avg_project_size = project_sizes[building_type]
            num_projects = total_volume // avg_project_size

            for _ in range(num_projects):
                buildings.append({
                    'type': building_type,
                    'gfa': avg_project_size
                })
        
        return buildings
    
    # generate building projects from volumens
    residential_buildings_dict = generate_projects(total_gfa_volumes,project_sizes)
    
    if residential_buildings_dict is not None and len(residential_buildings_dict) > 0:
        use_unit_size_policy = st.checkbox(unit_size_policy_selection[lin])
        if use_unit_size_policy:
            my_unit_size_policy = unit_size_policy_maker(lin=lin)
        else:
            my_unit_size_policy = None
    
    return residential_buildings_dict, my_unit_size_policy, pre_con_sim_time, num_comp, house_hold_shares_estimates, avg_family_size, apartment_efficiency_factor

def unit_size_policy_maker(lin=1):
            
    #LOCAT
    policy_input_title = ['Politiikkamuotoilu','Policy statement']
    policy_statements = [[["Asuntoja, jotka ovat **alle** (m2)...","..saa olla enintään (%)"],
                        ["Asuntoja, jotka ovat **yli** (m2)...","..tulee olla vähintään (%)"]],
                        [["Units which are **below** (m2)...","..may be at most (%)"],
                        ["Units which are **above** (m2)...","..must be at least (%)"]]]

    with st.container(border=True):
        st.markdown(policy_input_title[lin])

        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                size1 = st.slider(
                    policy_statements[lin][0][0],
                    20, 60, 30, step=5,
                    )
                pct1 = st.slider(
                    policy_statements[lin][0][1],
                    10, 80, 50, step=5
                    )

        with col2:
            with st.container(border=True):
                size2 = st.slider(
                    policy_statements[lin][1][0],
                    60, 120, 70, step=5
                    )
                pct2 = st.slider(
                    policy_statements[lin][1][1],
                    0, 100-pct1, int(round(((100-pct1)/2)/5)*5), step=5
                    )

    if pct1 + pct2 > 100:
        st.stop()

    my_policy_nums = [pct1, size1, pct2, size2]

    my_unit_size_policy = {
        'apartment-condo': [my_policy_nums[0], my_policy_nums[1], my_policy_nums[2], my_policy_nums[3]]
    }
    return my_unit_size_policy

def simulation_plot(sim_df,init_df=None,lin=1):
    #LOCAT
    yaxis_title_left = ['Vuosiasuntotuotanto (kem²)','Residential production (GFA)']
    yaxis_title_right = ['Asukasmäärän kasvu','Population increase']
    xaxis_title = ['Vuosi','Year']
    # translation of items
    col_translations = {
        'one-family-house':['Omakotitalot','One-family-house'],
        'multi-family-house':['Rivi/paritalot','Multi-family-house'],
        'apartment-condo':['Kerrostalot','Apartment-condo'],
        'families':['Perheissä asuvat','Family population'],
        'singles':['Yksin asuvat','Single population'],
        'other':['Muut','Other population']
    }

    #concat initial pop levels
    if init_df is None:
        init_year = sim_df['con_year'].min()
        data = {
            'con_year': [init_year-1],  # initial year
            'families': [0],  # initial count of families
            'singles': [0],   # initial count of singles
            'other': [0]  # initial count of others
        }
        init_df = pd.DataFrame(data)
    
    df = pd.concat([init_df, sim_df]).reset_index(drop=True)

    color_map = {
        'one-family-house': 'burlywood',
        'multi-family-house': 'peru',
        'apartment-condo': 'sienna'
    }

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    building_types = df['type'].unique()

    def get_histogram_bins(data):
        start = data.min() - 0.5  # Start half a year before the first year
        end = data.max() + 0.5    # End half a year after the last year
        return dict(start=start, end=end, size=1)

    for building_type in building_types:
        # Ensure building_type is a key in col_translations
        if building_type in col_translations:
            translated_name = col_translations[building_type][lin]
        else:
            translated_name = 'nan'  # Fallback if building_type is not found

        fig.add_trace(
            go.Histogram(
                name=translated_name,
                legendgroup='histo',
                x=df[df['type'] == building_type]['con_year'],
                y=df[df['type'] == building_type]['volume'],
                histfunc='sum',
                autobinx=False,
                xbins=get_histogram_bins(df[df['type'] == building_type]['con_year']),
                cumulative_enabled=False,
                marker=dict(color=color_map.get(building_type, 'brown'), opacity=0.9)
            ), secondary_y=False
        )
    fig.update_layout(barmode='stack')

    # ----------- POP LINES --------------

    # Calculate cumulative sums separately
    cumulative_data = {}
    for column in ['families', 'singles', 'other']:
        # Calculate cumulative sum, ensuring it only includes years with actual data
        cumulative_data[column] = df[df['volume'] > 0][column].cumsum()

    # Line plots for households
    lines = [('other', 'dot'), ('singles', 'dash'), ('families', 'solid')]
    for column, line_style in lines:
        # Get the cumulative data for the column
        column_cumulative_data = cumulative_data.get(column, [])

        fig.add_trace(
            go.Scatter(
                x=df[df['volume'] > 0]['con_year'],
                y=column_cumulative_data,
                mode='lines',
                name=col_translations[column][lin],
                legendgroup='lines',
                line=dict(color='black', width=1.0, dash=line_style),
                hoverinfo=None
            ), secondary_y=True
        )
    
    # Update axes
    year_now = datetime.datetime.now().year
    end_year = max(year_now, df['con_year'].max())

    # Create a range of years from the current year to the end year
    years_range = list(range(year_now, end_year + 1))

    # Update x-axis
    fig.update_xaxes(tickvals=years_range, ticktext=years_range,
                    range=[year_now - 0.5, end_year + 1.5],
                    title=xaxis_title[lin])

    #define first y-axis amx
    y1_max_value = df['volume'].max() * 1.5

    #define second y-axis max
    y2_max_value = max(np.cumsum(df['families']).max(), np.cumsum(df['singles']).max(), np.cumsum(df['other']).max())
    
    fig.update_yaxes(showgrid=True, zeroline=False)
    fig.update_yaxes(title=yaxis_title_left[lin]) #, secondary_y=False, range=[0, y1_max_value])
    fig.update_yaxes(title=yaxis_title_right[lin], secondary_y=True, range=[0, y2_max_value])

    # Legend and layout
    fig.update_layout(
        margin={"r": 10, "t": 10, "l": 10, "b": 10}, height=700,
        legend=dict(yanchor="top",y=0.95,xanchor="left",x=0.01)
        #legend=dict(yanchor="top", y=0.95, xanchor="right", x=0.90)
    )

    return fig