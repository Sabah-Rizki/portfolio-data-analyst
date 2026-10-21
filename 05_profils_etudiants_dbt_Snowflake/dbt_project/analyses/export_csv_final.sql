-- analyses/export_csv_final.sql
-- Requête d'export du livrable final (862 lignes) -- EXÉCUTÉE SUR DBT + SNOWFLAKE.
-- Une "analysis" dbt : compilée par dbt (dbt compile), puis lancée dans Snowflake
-- pour télécharger le CSV. Reste dans le projet dbt sans modifier les 4 marts.
-- Correction incluse : jointure région normalisée -> PACA +1,7 (et non -0,7).

with etudiants as (
    select AGE_GROUP, GENDER, REGION, YEAR_PATH_STARTED, count(*) as NB_ETUDIANTS
    from {{ ref('stg_students') }}
    group by 1, 2, 3, 4
),
insee_region as (
    select
        upper(replace(replace(REGION, '''', ''), ' ', '')) as region_key,
        PART_EMPLOI_NATIONAL_PCT as pct_emploi_france,
        PART_POP_NATIONALE_PCT   as pct_pop_france
    from {{ source('raw', 'INSEE_EMPLOI_REGION') }}
    where ANNEE = 2022
),
part_oc_region as (
    select REGION, YEAR_PATH_STARTED,
           round(sum(NB_ETUDIANTS) * 100.0
                 / sum(sum(NB_ETUDIANTS)) over (partition by YEAR_PATH_STARTED), 1) as pct_oc_region
    from etudiants group by 1, 2
),
ecart_region as (
    select p.REGION, p.YEAR_PATH_STARTED, i.pct_emploi_france, i.pct_pop_france,
           round(p.pct_oc_region - i.pct_emploi_france, 1) as ecart_vs_emploi_france
    from part_oc_region p
    left join insee_region i
        on upper(replace(replace(p.REGION, '''', ''), ' ', '')) = i.region_key
)
select e.AGE_GROUP, e.GENDER, e.REGION, e.YEAR_PATH_STARTED, e.NB_ETUDIANTS,
       r.pct_emploi_france      as INSEE_PCT_EMPLOI_REGION,
       r.pct_pop_france         as INSEE_PCT_POP_REGION,
       r.ecart_vs_emploi_france as ECART_VS_EMPLOI_FRANCE
from etudiants e
left join ecart_region r
    on e.REGION = r.REGION and e.YEAR_PATH_STARTED = r.YEAR_PATH_STARTED
order by e.YEAR_PATH_STARTED, e.REGION, e.AGE_GROUP, e.GENDER
