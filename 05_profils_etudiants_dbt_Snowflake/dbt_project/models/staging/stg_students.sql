with source as (
    select * from {{ source('raw', 'STUDENTS_RAW') }}
),

cleaned as (
    select
        USER_ID,
        PATH_CATEGORY_NAME,
        AGE_GROUP,
        coalesce(GENDER, 'Non renseigné') as GENDER,
        REGION,
        YEAR_PATH_STARTED,
        2025 - YEAR_PATH_STARTED as YEARS_SINCE_START
    from source
    where YEAR_PATH_STARTED between 2022 and 2025
)

select * from cleaned