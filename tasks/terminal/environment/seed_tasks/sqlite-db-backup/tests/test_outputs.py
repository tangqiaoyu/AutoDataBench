import os
import sqlite3
import shutil

def test_sqlite_backup():
    """Test that the SQLite database was backed up successfully"""
    original_db_path = "/app/data/sql_query_manager.db"
    backup_db_path = "/app/data/sql_query_manager_backup.db"
    
    # Check that both files exist
    assert os.path.exists(original_db_path), "Original database file does not exist"
    assert os.path.exists(backup_db_path), "Backup database file was not created"
    
    # Check that both files are valid SQLite databases
    def is_valid_sqlite_db(file_path):
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            conn.close()
            return True
        except sqlite3.Error:
            return False
    
    assert is_valid_sqlite_db(original_db_path), "Original database is not a valid SQLite file"
    assert is_valid_sqlite_db(backup_db_path), "Backup database is not a valid SQLite file"
    
    # Check that both files have the same size (indicating successful copy)
    original_size = os.path.getsize(original_db_path)
    backup_size = os.path.getsize(backup_db_path)
    assert original_size == backup_size, f"Backup file size ({backup_size}) differs from original ({original_size})"
    
    # Check that both databases have the same table structure
    def get_table_info(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        table_info = {}
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name});")
            table_info[table_name] = cursor.fetchall()
        conn.close()
        return table_info
    
    original_tables = get_table_info(original_db_path)
    backup_tables = get_table_info(backup_db_path)
    
    assert original_tables == backup_tables, "Table structures differ between original and backup databases"
