with students as (
    select * from {{ ref('stg_students') }}
),

aggregated as (
    select
        YEAR_PATH_STARTED,
        GENDER,
        count(*) as nb_etudiants
    from students
    group by YEAR_PATH_STARTED, GENDER
)

select * from aggregated
order by YEAR_PATH_STARTED, GENDER