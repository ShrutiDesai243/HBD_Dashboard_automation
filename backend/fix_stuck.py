from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.getcwd())
load_dotenv()
from config import config
from tasks.gdrive_task.etl_tasks import get_service, process_csv_task

engine = create_engine(config.DATABASE_URI)
with engine.connect() as conn:
    # Stuck files dekho
    stuck = conn.execute(text(
        "SELECT drive_file_id, filename, drive_folder_id FROM file_registry WHERE status='IN_PROGRESS'"
    )).fetchall()
    print(f"Stuck IN_PROGRESS files: {len(stuck)}")
    
    # Pehle PENDING reset karo
    conn.execute(text(
        "UPDATE file_registry SET status='PENDING' WHERE status='IN_PROGRESS'"
    ))
    conn.commit()
    print("Reset to PENDING done!")

    # Ab queue mein push karo
    service = get_service()
    count = 0
    for file_id, filename, folder_id in stuck:
        try:
            file_meta = service.files().get(fileId=file_id, fields="id,name,modifiedTime,parents").execute()
            modified_time = file_meta.get('modifiedTime')
            file_name = file_meta.get('name') or filename
            f_id = file_meta.get('parents', [folder_id])[0]
            process_csv_task.delay(file_id, file_name, f_id, None, None, modified_time)
            print(f"  [+] Queued: {file_name}")
            count += 1
        except Exception as e:
            print(f"  [!] Error {filename}: {e}")
    
    print(f"\nTotal queued: {count} files")