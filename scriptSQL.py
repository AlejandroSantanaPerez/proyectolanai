import pyodbc
import pandas as pd
import pytz
from datetime import datetime, timedelta

# Database Connection (Replace placeholders)
def run_query():
    connection_string = 'Driver={ODBC Driver 18 for SQL Server};Server=tcp:servidorcloudcomputing.database.windows.net,1433;Database=ProyectoFinal;Uid=CloudSAc56aa020;Pwd=Asdf123.;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

    # SQL Query with WET Time Zone (Replace placeholders if needed)
    sql_query = """
    WITH RankedTrips AS (
        SELECT 
            trip_id, 
            arrival_time, 
            stop_id, 
            stop_sequence,
            ROW_NUMBER() OVER (PARTITION BY stop_id ORDER BY arrival_time) AS rn, -- Rank stops per stop_id
            CASE stop_id -- Create a custom sort order
                WHEN 9181 THEN 1
                WHEN 9385 THEN 2
                WHEN 9386 THEN 3
                WHEN 9387 THEN 4
                WHEN 2670 THEN 5
                WHEN 1279 THEN 6
                WHEN 1280 THEN 7
                WHEN 1281 THEN 8
                WHEN 1282 THEN 9
                WHEN 2533 THEN 10
                WHEN 2625 THEN 11
            END AS stop_order
        FROM stop_times
        WHERE 
        TRY_CONVERT(TIME, arrival_time) IS NOT NULL AND
        TRY_CONVERT(DATETIME, CONCAT(CONVERT(DATE, GETDATE()), ' ', arrival_time)) 
            AT TIME ZONE 'GMT Standard Time' BETWEEN -- Convert to WET
            CONVERT(DATETIME, GETDATE() AT TIME ZONE 'GMT Standard Time') 
            AND DATEADD(minute, 30, CONVERT(DATETIME, GETDATE() AT TIME ZONE 'GMT Standard Time'))
        AND trip_id IN (
            SELECT trip_id
            FROM trips
            WHERE route_id = '16' 
            AND service_id IN (
                SELECT service_id
                FROM calendar_dates
                WHERE date = FORMAT(GETDATE() AT TIME ZONE 'GMT Standard Time', 'yyyyMMdd')
            )
        )
        AND stop_id IN (9181, 9385, 9386, 9387, 2670, 1279, 1280, 1281, 1282, 2533, 2625)
    )
    SELECT trip_id, arrival_time, stop_id, stop_sequence
    FROM RankedTrips
    WHERE rn = 1
    ORDER BY stop_order; -- Order by the custom stop_order

    """

    # Execute Query and Fetch Results
    with pyodbc.connect(connection_string) as conn:
        df = pd.read_sql_query(sql_query, conn)

    # Convert stop_id to string before creating dictionaries
    df['stop_id'] = df['stop_id'].astype(str)  

    # Create List of Dictionaries
    arrival_list = df[['arrival_time', 'stop_id']].to_dict(orient='records')

    return arrival_list

def calculate_time_difference(arrival_time_str):
    """Calculates the time difference in minutes between the current time in WEST 
    and the given arrival time string.

    Args:
        arrival_time_str (str): The arrival time in the format 'HH:MM:SS'.

    Returns:
        int: The time difference in minutes, or None if there's an error.
    """

    try:
        now_wet = datetime.now(pytz.timezone('Atlantic/Canary'))
        arrival_datetime = datetime.strptime(f"{now_wet.date()} {arrival_time_str}", "%Y-%m-%d %H:%M:%S")
        arrival_datetime_wet = pytz.timezone('Atlantic/Canary').localize(arrival_datetime)

        arrival_datetime_wet += timedelta(days=1) if arrival_datetime_wet < now_wet else timedelta(0)
        
        # Calculate the time difference in minutes and handle negative values
        time_difference = arrival_datetime_wet - now_wet
        minutes_difference = max(0, time_difference.total_seconds() / 60)  # Ensure non-negative
        
        return int(minutes_difference)

    except ValueError:
        print("Error: Invalid time format. Please use 'HH:MM:SS'.")
        return None