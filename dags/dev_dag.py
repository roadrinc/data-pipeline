from datetime import datetime, timedelta

from airflow.models import DAG
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.email import EmailOperator
from airflow.operators.empty import EmptyOperator

from development.mongodb_api import _fetch_mongo_api_to_json, _transform_users_to_csv
from development.rdstationcmr_api import (
    _fetch_rdstudioapicmr_contacts_to_json,
    _transform_contacts_to_csv,
)

from helpers.variables_mongodb_api import _create_users_sql_table, _users_colum_names
from helpers.variables_rdstation_api import (
    _create_contacts_sql_table,
    _contacts_colum_names,
)
from helpers.dev_helpers import _create_sql_file, _inject_sql_file_to_postgres

TOKEN = "63fec468e1dca1000c53a7e5"


default_args = {
    "owner": "jorgeav527",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email": "jv@roadr.com",
    "email_on_success": False,
    "email_on_failure": False,
    "ds": "{{ ds }}",
}

with DAG(
    default_args=default_args,
    dag_id="ETL_develoment_v11",
    start_date=datetime(2023, 4, 1),
    schedule_interval="@daily",  # will be "@daily"
    catchup=True,
    tags=["rd_studio_api"],
    template_searchpath="bucket",
) as dag:
    ####################################################
    ##### CONTACTS (RD Station CMR API (contacts)) #####
    ####################################################

    # Define the HttpSensor to check if the connection is OK
    check_api_rdstationcmr_connection = HttpSensor(
        task_id="check_api_rdstationcmr_connection",
        http_conn_id="RD_Studio_API",  # https://crm.rdstation.com/api/v1/contacts?token=MyToken&page=Page&limit=Limit&q=Query
        endpoint=f"contacts?token={TOKEN}",
        response_check=lambda response: response.status_code == 200,
        poke_interval=60,  # check the API connection every 60 seconds
        timeout=120,  # wait up to 120 seconds for a successful connection
    )

    # Define the PythonOperator to fetch and save contacts
    fetch_rdstudioapicmr_contacts_to_json = PythonOperator(
        task_id="fetch_rdstudioapicmr_contacts_to_json",
        python_callable=_fetch_rdstudioapicmr_contacts_to_json,
        op_kwargs={
            "extracted_path": "bucket/extracted_data/rdstationcmr_contacts_{{ds}}.json",
            # "contacts_url": "https://crm.rdstation.com/api/v1/contacts?token={TOKEN}",
        },
    )

    # Define the PythonOperator to transform and save contacts
    transform_contacts_to_csv = PythonOperator(
        task_id="transform_contacts_to_csv",
        python_callable=_transform_contacts_to_csv,
        op_kwargs={
            "extracted_path": "bucket/extracted_data/rdstationcmr_contacts_{{ds}}.json",
            "transformed_path": "bucket/transformed_data/rdstationcmr_contacts_{{ds}}.csv",
        },
    )

    # Define the PythonOperator to create contacts SQL table
    create_contacts_sql_table = PostgresOperator(
        task_id="create_contacts_sql_table",
        postgres_conn_id="Postgres_ID",
        sql=_create_contacts_sql_table,
    )

    # Create a PythonOperator to create a sql file
    create_sql_contacts = PythonOperator(
        task_id="create_sql_contacts",
        python_callable=_create_sql_file,
        op_kwargs={
            "columns": _contacts_colum_names,
            "transformed_path": "bucket/transformed_data/rdstationcmr_contacts_{{ds}}.csv",
            "loaded_path": "bucket/loaded_data/rdstationcmr_contacts_{{ds}}.sql",
            "table_name": "contacts",
        },
    )

    # Inject the sql file into PostgresDB
    insert_contacts_to_postgres = PythonOperator(
        task_id="insert_contacts_to_postgres",
        python_callable=_inject_sql_file_to_postgres,
        op_kwargs={
            "loaded_path": "bucket/loaded_data/rdstationcmr_contacts_{{ds}}.sql",
        },
    )

    ##################################
    ##### USERS (mongoDB(users)) #####
    ##################################

    # Set up the MongoDb API Sensor operator
    check_mongodb_api_connection = HttpSensor(
        task_id="check_mongodb_api_connection",
        http_conn_id="Mongo_DB_API",
        endpoint="api/user/allusers",
        headers={
            "x-auth-token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiNjNjODY1ZjM1M2JkZjgyMGY5MjgxNjRjIn0sImlhdCI6MTY3OTM1ODE3N30.krlGV2QiC_KwGcVW38TrlszIPDnb6RSX_ML1Kt206YA"
        },
        response_check=lambda response: response.status_code == 200,
        poke_interval=60,  # check the API connection every 60 seconds
        timeout=120,  # wait up to 120 seconds for a successful connection
    )

    # Define the PythonOperator to fetch and save users
    fetch_mongo_api_to_json = PythonOperator(
        task_id="fetch_mongo_api_to_json",
        python_callable=_fetch_mongo_api_to_json,
        op_kwargs={
            "extracted_path": "bucket/extracted_data/mongodb_api_users_{{ds}}.json",
            "users_url": "http://192.168.0.13:3000/api/user/allusers?start_day=2022-07-27&end_day=2022-07-28{{data_interval_start}}",
        },
    )

    # Define the PythonOperator to transform and save users
    transform_users_to_csv = PythonOperator(
        task_id="transform_users_to_csv",
        python_callable=_transform_users_to_csv,
        op_kwargs={
            "extracted_path": "bucket/extracted_data/mongodb_api_users_{{ds}}.json",
            "transformed_path": "bucket/transformed_data/mongodb_api_users_{{ds}}.csv",
        },
    )

    # Define the PythonOperator to create users SQL table
    create_users_sql_table = PostgresOperator(
        task_id="create_users_sql_table",
        postgres_conn_id="Postgres_ID",
        sql=_create_users_sql_table,
    )

    # Create a PythonOperator to create a sql file
    create_sql_users = PythonOperator(
        task_id="create_sql_users",
        python_callable=_create_sql_file,
        op_kwargs={
            "columns": _users_colum_names,
            "transformed_path": "bucket/transformed_data/mongodb_api_users_{{ds}}.csv",
            "loaded_path": "bucket/loaded_data/mongodb_api_users_{{ds}}.sql",
            "table_name": "users",
        },
    )

    # Inject the sql file into PostgresDB
    insert_users_to_postgres = PythonOperator(
        task_id="insert_users_to_postgres",
        python_callable=_inject_sql_file_to_postgres,
        op_kwargs={
            "loaded_path": "bucket/loaded_data/mongodb_api_users_{{ds}}.sql",
        },
    )

    ##################################
    ##### Others #####
    ##################################

    # Empty operator
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    # Send report as a email status
    send_email_report_status = EmailOperator(
        task_id="send_email_report_status",
        to="jv@roadr.com",
        subject="Airflow Report - {{ ds }}",
        html_content="""<h3>Task Report for {{ ds }}</h3>
                    <p>Successful tasks:</p>
                    <ul>
                        {% for task in dag.tasks %}
                            {% if task.task_id != 'send_email' and task.task_id.endswith('_success') %}
                                <li>{{ task.task_id }} - {{ task.execution_date }}</li>
                            {% endif %}
                        {% endfor %}
                    </ul>""",
    )

    start >> [check_api_rdstationcmr_connection, check_mongodb_api_connection]
    (
        check_api_rdstationcmr_connection
        >> fetch_rdstudioapicmr_contacts_to_json
        >> transform_contacts_to_csv
        >> create_contacts_sql_table
        >> create_sql_contacts
        >> insert_contacts_to_postgres
    )
    (
        check_mongodb_api_connection
        >> fetch_mongo_api_to_json
        >> transform_users_to_csv
        >> create_users_sql_table
        >> create_sql_users
        >> insert_users_to_postgres
    )
    (
        [
            insert_contacts_to_postgres,
            insert_users_to_postgres,
        ]
        >> send_email_report_status
        >> end
    )