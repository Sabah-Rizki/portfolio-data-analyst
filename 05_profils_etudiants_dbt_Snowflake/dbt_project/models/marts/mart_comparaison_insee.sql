-- Modèle de comparaison OC vs INSEE
-- Compare le profil des étudiants OC avec les données nationales INSEE
-- Corrections : (1) code mort retiré (CTE âge non utilisées) ;
--               (2) jointure région normalisée pour gérer la différence de libellé
--                   "Côte d'Azur" (OC) vs "Côte d Azur" (INSEE) -> répare PACA.

with insee_region as (
    select
        REGION,
        PART_EMPLOI_NATIONAL_PCT as pct_emploi_france,
        PART_POP_NATIONALE_PCT as pct_pop_france
    from {{ source('raw', 'INSEE_EMPLOI_REGION') }}
    where ANNEE = 2022
),

etudiants_region as (
    select
        REGION,
        sum(NB_ETUDIANTS) as nb_etudiants_oc,
        round(sum(NB_ETUDIANTS) * 100.0 / sum(sum(NB_ETUDIANTS)) over (), 1) as pct_oc
    from {{ ref('mart_region') }}
    where YEAR_PATH_STARTED = 2025
    group by REGION
),

comparaison_region as (
    select
        e.REGION,
        e.nb_etudiants_oc,
        e.pct_oc as pct_etudiants_oc,
        i.pct_emploi_france,
        i.pct_pop_france,
        round(e.pct_oc - i.pct_emploi_france, 1) as ecart_vs_emploi_france
    from etudiants_region e
    left join insee_region i
        on upper(replace(replace(e.REGION, '''', ''), ' ', ''))
         = upper(replace(replace(i.REGION, '''', ''), ' ', ''))
)

select * from comparaison_region
order by pct_etudiants_oc desc
