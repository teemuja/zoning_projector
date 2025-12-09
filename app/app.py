# beta version of zoning projector app
import streamlit as st
import pandas as pd
import sim, projector_summary

st.set_page_config(page_title="Zoning Projector", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricDelta"] svg {
            display: none;}
    .stProgress .st-bo {
        background-color: green;
    }
    </style>
    """, unsafe_allow_html=True)


# ----------- APP ------------
    
#LOCAT
title_text = ["Kaavoitusprojektori", "Zoning Projector"]
tot_pop_metric_text = ["Väestökasvu", "Total Population growth"]

options = {"FIN": 0,
        "ENG": 1 }
selection = st.segmented_control("", options.keys(), selection_mode="single", default="FIN",key="lang")
title_holder = st.empty()

if selection is None:
    lin = 0
    with title_holder:
        st.header(title_text[0], divider="red")
else:
    lin = options[selection]
    with title_holder:
        st.header(title_text[lin], divider="red")

st.caption("Version 0.94.8.19 'Meurman'")

tab1, tab2 = st.tabs(["Projektori","Dokumentaatio"] if lin==0 else ["Projector","Documentation"])

with tab1:

    # Conceptor ..basic and enhanced
    residential_buildings_dict, my_unit_size_policy, pre_con_sim_time, num_comp, house_hold_shares_estimates, avg_family_size, apartment_efficiency_factor = sim.conceptor(lin=lin)
    
    my_params = {
        "buildings": residential_buildings_dict,
        "pre_con_time": int(pre_con_sim_time),
        "construction_times": None,
        "num_companies": int(num_comp),
        "unit_size_policy": my_unit_size_policy,
        "household_shares_estimates": house_hold_shares_estimates,
        "avg_family_size": avg_family_size,
        "apt_efficiency": apartment_efficiency_factor
    }

    CONSIM_respond = sim.main_sim(args=my_params) #move to API later
    sim_df = pd.DataFrame(CONSIM_respond.get('body'))

    with st.container(border=True):
        st.plotly_chart(sim.simulation_plot(sim_df,lin=options[selection]), use_container_width=True, config = {'displayModeBar': False})
        
        #st.dataframe(sim_df)#[['avg_unit_size','families','singles','other']].describe(), use_container_width=True)
        
        cols = ['families', 'singles', 'other']
        pop_sum = sim_df[cols].sum().sum()
        gfa_sum = sim_df['volume'].sum()
        def fmt(x): return f"{int(x):,}".replace(",", " ")
        gfa_sum = fmt(gfa_sum)

        con_time_tot = sim_df[sim_df['volume']>0]['con_year'].max() - (sim_df[sim_df['volume']>0]['con_year'].min() -1)
        metric_title = [f" {tot_pop_metric_text[lin]} ({con_time_tot}v)",
                        f" {tot_pop_metric_text[lin]} ({con_time_tot}yr)"]
        metric_help_text = ["Väestöennuste huomioi eri asuntotyyppien erilaiset kotitalouskoot, jolloin arvio on tarkempi kuin perinteinen kerrosalapohjainen arvio.",
                            "Population projection accounts for varied household sizes, making the estimate more accurate than just GFA-based estimates."]
        
        
        st.metric(metric_title[lin], value=round(pop_sum,-1),delta=f"{gfa_sum} kem²", help=metric_help_text[lin])

        # DL
        @st.cache_data
        def convert_for_download(df):
            return df.to_csv().encode("utf-8")
        
        from datetime import datetime
        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y-%H-%M-%S")
        
        #concat initial pop levels
        def get_summary_df(sim_df=None):
            init_year = sim_df['con_year'].min()
            data = {
                'con_year': [init_year-1],  # initial year
                'families': [0],  # initial count of families
                'singles': [0],   # initial count of singles
                'other': [0]  # initial count of others
            }
            init_df = pd.DataFrame(data)
            df = pd.concat([init_df, sim_df]).reset_index(drop=True)
            return df
        
        summary_df = get_summary_df(sim_df.drop(columns=['project_id','avg_unit_size','company']))
        cols = ['con_year','type','volume','families', 'singles', 'other']
        summary_df = summary_df[cols].rename(columns={'con_year':'Year','type':'Building Type','volume':'GFA (m²)','families':'Family population','singles':'Single population','other':'Other population'})
        csv = convert_for_download(summary_df)

        st.download_button(
            label="Lataa ennuste CSV-tiedostona" if lin==0 else "Download projection as CSV file",
            data=csv,
            file_name=f"projector_projection_{date_time}.csv",
            mime="text/csv",
            icon=":material/download:",
            disabled=False
        )

    
with tab2:
    md_text = projector_summary.projector_summary(lin=lin)
    st.markdown(md_text)
            

# ----------- FOOTER -----------

st.markdown('###')
st.markdown('---')
# https://img.shields.io/github/license/:teemuja/:zoning_projector

license = f'''
        <a href="https://share.streamlit.io/user/teemuja" target="_blank">
            <img src="https://img.shields.io/badge/&copy;-teemuja-fab43a" alt="teemuja" title="Teemu Jama">
        </a>
        '''
st.markdown(license, unsafe_allow_html=True)