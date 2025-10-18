import csv
from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://53ed6a0b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

BATCH_SIZE = 500  # number of rows per transaction


def load_csv(file_path, callback):
    """Read a CSV and yield rows as dicts"""
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                callback(batch)
                batch = []
        if batch:
            callback(batch)


def upload_farms(file_path):
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                tx.run(
                    """
                    MERGE (f:Farm {id: $id})
                    SET f.name = $name,
                        f.coordinates = $coordinates
                    """,
                    id=row['id'],
                    name=row.get('name', ''),
                    coordinates=row.get('coordinates', '')
                )
            tx.commit()
    load_csv(file_path, insert)
    print("Farms uploaded.")


def upload_animals(file_path):
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                tx.run(
                    """
                    MERGE (a:Animal {id: $id})
                    SET a.id_api = $id_api,
                        a.name = $name,
                        a.birth = $birth,
                        a.type = $type,
                        a.sex = $sex,
                        a.breed = $breed,
                        a.breed_short = $breed_short
                    WITH a
                    MATCH (f:Farm {id: $farm_id})
                    MERGE (a)-[:BELONGS_TO]->(f)
                    """,
                    id=row['id'],
                    id_api=row.get('id_api'),
                    name=row.get('name'),
                    birth=row.get('birth'),
                    type=row.get('type'),
                    sex=row.get('sex'),
                    breed=row.get('breed'),
                    breed_short=row.get('breed_short'),
                    farm_id=row.get('farm_id')
                )
            tx.commit()
    load_csv(file_path, insert)
    print("Animals uploaded.")


def upload_devices(file_path):
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                tx.run(
                    """
                    MERGE (d:Device {id: $id})
                    SET d.type = $type
                    WITH d
                    MATCH (a:Animal {id_api: $id_animal})
                    MERGE (d)-[:ATTACHED_TO]->(a)
                    """,
                    id=row['id'],
                    type=row.get('type'),
                    id_animal=row.get('id_animal')
                )
            tx.commit()
    load_csv(file_path, insert)
    print("Devices uploaded.")


def upload_device_data(file_path):
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                tx.run(
                    """
                    MERGE (dd:DeviceData {id: $id})
                    SET dd.created = $created,
                        dd.acc_x = toFloat($acc_x),
                        dd.acc_y = toFloat($acc_y),
                        dd.acc_z = toFloat($acc_z),
                        dd.std_x = toFloat($std_x),
                        dd.std_y = toFloat($std_y),
                        dd.std_z = toFloat($std_z),
                        dd.max_x = toFloat($max_x),
                        dd.max_y = toFloat($max_y),
                        dd.max_z = toFloat($max_z),
                        dd.temperature = toFloat($temperature),
                        dd.coordinates = $coordinates
                    WITH dd
                    MATCH (d:Device {id: $id_api})
                    MERGE (dd)-[:FROM_DEVICE]->(d)
                    """,
                    id=row['id'],
                    created=row.get('created'),
                    acc_x=row.get('acc_x', '0'),
                    acc_y=row.get('acc_y', '0'),
                    acc_z=row.get('acc_z', '0'),
                    std_x=row.get('std_x', '0'),
                    std_y=row.get('std_y', '0'),
                    std_z=row.get('std_z', '0'),
                    max_x=row.get('max_x', '0'),
                    max_y=row.get('max_y', '0'),
                    max_z=row.get('max_z', '0'),
                    temperature=row.get('temperature', '0'),
                    coordinates=row.get('coordinates', ''),
                    id_api=row.get('id_api')
                )
            tx.commit()
    load_csv(file_path, insert)
    print("Device data uploaded.")

def upload_meteo_data(file_path):
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                # create unique id if missing
                meteo_id = (
                    row.get("id")
                    or f"{row.get('farm_id_api','unknown')}_{row.get('station_timedata','unknown')}"
                )

                tx.run(
                    """
                    MERGE (m:MeteoData {id: $id})
                    SET m.station_timedata = $station_timedata,
                        m.crawled = $crawled,
                        m.station_city = $station_city,
                        m.station_nomos = $station_nomos,
                        m.longitude = $longitude,
                        m.latitude = $latitude,
                        m.temperature = toFloat($temperature),
                        m.humidity = toFloat($humidity),
                        m.wind = toFloat($wind),
                        m.direction = $direction,
                        m.yetos = toFloat($yetos),
                        m.barometer = toFloat($barometer),
                        m.dew_point = toFloat($dew_point),
                        m.heat_index = toFloat($heat_index),
                        m.wind_chill = toFloat($wind_chill),
                        m.solar_radiation = toFloat($solar_radiation)
                    WITH m
                    MATCH (f:Farm {id_api: $farm_id_api})
                    MERGE (m)-[:FROM_FARM]->(f)
                    """,
                    id=meteo_id,
                    station_timedata=row.get('station_timedata'),
                    crawled=row.get('crawled'),
                    station_city=row.get('station_city'),
                    station_nomos=row.get('station_nomos'),
                    longitude=row.get('longitude'),
                    latitude=row.get('latitude'),
                    temperature=row.get('temperature', '0'),
                    humidity=row.get('humidity', '0'),
                    wind=row.get('wind', '0'),
                    direction=row.get('direction'),
                    yetos=row.get('yetos', '0'),
                    barometer=row.get('barometer', '0'),
                    dew_point=row.get('dew_point', '0'),
                    heat_index=row.get('heat_index', '0'),
                    wind_chill=row.get('wind_chill', '0'),
                    solar_radiation=row.get('solar_radiation', '0'),
                    farm_id_api=row.get('farm_id_api')
                )
            tx.commit()
    load_csv(file_path, insert)
    print("Meteo data uploaded.")



def upload_farm_contacts(file_path):
    """Upload farm_contacts.csv defining distances between sheep in the same farm."""
    def insert(batch):
        with driver.session(database=NEO4J_DATABASE) as session:
            tx = session.begin_transaction()
            for row in batch:
                try:
                    tx.run(
                        """
                        MATCH (a1:Animal {id_api: $sheep1}),
                              (a2:Animal {id_api: $sheep2})
                        WHERE a1 <> a2
                        MERGE (a1)-[r:CLOSE_TO]->(a2)
                        SET r.distance = toFloat($distance),
                            r.unit = coalesce($unit, 'm')
                        """,
                        sheep1=row.get("sheep1_id_api") or row.get("id_api_1"),
                        sheep2=row.get("sheep2_id_api") or row.get("id_api_2"),
                        distance=row.get("distance", "0"),
                        unit=row.get("unit", "m")
                    )
                except Exception as e:
                    print("Error linking sheep:", e)
            tx.commit()
    load_csv(file_path, insert)
    print("Farm contacts uploaded.")

if __name__ == "__main__":
    upload_farms("farms.csv")
    upload_animals("animals.csv")
    upload_devices("devices.csv")
    # Skip device_data for now
    # upload_device_data("device_data.csv")
    # upload_meteo_data("meteo_data.csv")
    upload_farm_contacts("farm_contacts.csv")
    print("All CSVs uploaded (excluding device_data).")
    driver.close()
