import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from azure.data.tables import TableServiceClient, UpdateMode
import os

# -----------------------
# Azure Table Storage konfigurieren
# -----------------------
connection_string = st.secrets["AZURE_CONN_STR"]
table_name = "BackupStatus"

service = TableServiceClient.from_connection_string(connection_string)
table_client = service.get_table_client(table_name)

# -----------------------
# Hilfsfunktionen
# -----------------------
def load_backups():
    """Alle Backups und Restores aus Table Storage laden"""
    entities = list(table_client.list_entities())
    backups = []
    for e in entities:
        progress = float(e.get("Fortschritt", 0.0) or 0.0)
        backups.append({
            "BackupID": e["RowKey"],
            "Typ": e["PartitionKey"],
            "Maschine": e.get("Maschine", ""),
            "Benutzer": e.get("Benutzer", ""),
            "Status": e.get("Status", ""),
            "Fortschritt": progress,
            "Restdaten": e.get("Restdaten", ""),
            "Restzeit": e.get("Restzeit", ""),
            "Startzeit": e.get("Startzeit", ""),
            "Endzeit": e.get("Endzeit", "")
        })
    return backups

def delete_backup_id(backup_id):
    """Backup + Restore löschen"""
    try:
        table_client.delete_entity(partition_key="Backup", row_key=backup_id)
    except:
        pass
    try:
        table_client.delete_entity(partition_key="Restore", row_key=backup_id)
    except:
        pass
    st.success(f"BackupID {backup_id} (Backup + Restore) wurde gelöscht!")

def assign_restore(backup_id, ziel_maschine):
    """Restore-Zuweisung erstellen"""
    try:
        backup_entity = table_client.get_entity(partition_key="Backup", row_key=backup_id)
    except:
        st.warning(f"BackupID {backup_id} existiert nicht.")
        return

    # Prüfen, ob Restore schon existiert
    try:
        existing_restore = table_client.get_entity(partition_key="Restore", row_key=backup_id)
        st.warning(f"Restore für BackupID {backup_id} ist bereits der Maschine {ziel_maschine} zugewiesen.")
        return
    except:
        pass  # Restore existiert noch nicht

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_restore = {
        "PartitionKey": "Restore",
        "RowKey": backup_id,
        "Maschine": ziel_maschine,
        "Benutzer": backup_entity.get("Benutzer", ""),
        "Status": "Zugewiesen",
        "Fortschritt": 0.0,
        "Restdaten": backup_entity.get("Restdaten", ""),
        "Restzeit": backup_entity.get("Restzeit", ""),
        "Startzeit": now_str,
        "Endzeit": backup_entity.get("Endzeit", "")
    }
    table_client.upsert_entity(new_restore)
    st.success(f"Restore für BackupID {backup_id} → Zielmaschine {ziel_maschine} zugewiesen.")

# -----------------------
# Streamlit UI
# -----------------------
st.title("💾 Backup & Restore Dashboard (Azure Version)")
st.caption("Backups laufen extern. Restores werden zugewiesen und Fortschritt wird live angezeigt.")

# Auto-Refresh alle 5 Sekunden
st_autorefresh(interval=1000, key="datarefresh")

# -----------------------
# Restore-Zuweisung Formular
# -----------------------
with st.form("restore_assign_form"):
    st.subheader("🔁 Restore zuweisen")
    backup_id_input = st.text_input("BackupID eines fertigen Backups")
    neue_vm_input = st.text_input("Zielmaschine für Restore")
    submit_restore = st.form_submit_button("Restore zuweisen")
    if submit_restore and backup_id_input and neue_vm_input:
        assign_restore(str(backup_id_input), neue_vm_input)

# -----------------------
# Backups + Restores anzeigen
# -----------------------
entities = load_backups()
if not entities:
    st.info("Keine Backups oder Restores gefunden.")
else:
    backup_ids = sorted(set([e["BackupID"] for e in entities]))
    for bid in backup_ids:
        st.markdown(f"### 🔹 BackupID: {bid}")
        delete_key = f"delete_{bid}"
        if st.button(f"❌ BackupID {bid} löschen (Backup + Restore)", key=delete_key):
            delete_backup_id(bid)

        for e in entities:
            if e["BackupID"] != bid:
                continue
            progress = min(max(e["Fortschritt"], 0.0), 1.0)
            st.write(
                f"{e['Typ']} – Maschine: {e['Maschine']} – Benutzer: {e['Benutzer']} | "
                f"Status: {e['Status']} | Fortschritt: {progress*100:.1f}% | "
                f"Restdaten: {e['Restdaten']} | Restzeit: {e['Restzeit']} | "
                f"Startzeit: {e['Startzeit']} | Endzeit: {e['Endzeit']}"
            )
            st.progress(progress)
