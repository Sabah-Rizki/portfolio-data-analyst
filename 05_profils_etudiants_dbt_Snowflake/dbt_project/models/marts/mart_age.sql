with students as (
    select * from {{ ref('stg_students') }}
),

aggregated as (
    select
        YEAR_PATH_STARTED,
        AGE_GROUP,
        count(*) as nb_etudiants
    from students
    group by YEAR_PATH_STARTED, AGE_GROUP
)

select * from aggregated
order by YEAR_PATH_STARTED, AGE_GROUP