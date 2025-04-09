from flask import Flask, render_template, request, redirect
from sqlalchemy import create_engine, text
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from config import SQLALCHEMY_DATABASE_URI, BLOB_ACCOUNT_NAME, BLOB_ACCOUNT_KEY, BLOB_CONTAINER

app = Flask(__name__)

# Azure SQL connection
engine = create_engine(SQLALCHEMY_DATABASE_URI)

# Azure Blob setup
blob_service = BlobServiceClient(
    account_url=f"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net",
    credential=BLOB_ACCOUNT_KEY
)
container_client = blob_service.get_container_client(BLOB_CONTAINER)

@app.route('/')
def index():
    edit_id = request.args.get("edit_id", type=int)
    with engine.connect() as conn:
        notes = conn.execute(text("SELECT * FROM Notes ORDER BY created_at DESC")).fetchall()
    return render_template("index.html", notes=notes, edit_id=edit_id, blob_account=BLOB_ACCOUNT_NAME, blob_container=BLOB_CONTAINER)

@app.route('/add', methods=['POST'])
def add_note():
    title = request.form['title']
    content = request.form['content']
    file = request.files['file']
    filename = None

    if file and file.filename:
        filename = file.filename
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        file_url = f"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net/{BLOB_CONTAINER}/{filename}"

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO Notes (title, content, filename, file_url, created_at)
            VALUES (:title, :content, :filename, :file_url, :created_at)
        """), {"title": title, "content": content, "filename": filename, "file_url": file_url, "created_at": datetime.now()})

    return redirect('/')

@app.route('/edit/<int:id>')
def edit_note(id):
    return redirect(f"/?edit_id={id}")

@app.route('/update/<int:id>', methods=['POST'])
def update_note(id):
    title = request.form['title']
    content = request.form['content']
    file = request.files['file']
    filename = None

    if file and file.filename:
        filename = file.filename
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        file_url = f"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net/{BLOB_CONTAINER}/{filename}"

    with engine.begin() as conn:
        if filename:
            conn.execute(text("""
                UPDATE Notes SET title = :title, content = :content, filename = :filename, file_url = :file_url WHERE id = :id
            """), {"title": title, "content": content, "filename": filename,  "file_url": file_url, "id": id})
        else:
            conn.execute(text("""
                UPDATE Notes SET title = :title, content = :content WHERE id = :id
            """), {"title": title, "content": content, "id": id})

    return redirect('/')

@app.route('/delete/<int:id>', methods=['POST'])
def delete_note(id):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT filename FROM Notes WHERE id = :id"), {"id": id}).fetchone()
        filename = result.filename if result else None
        conn.execute(text("DELETE FROM Notes WHERE id = :id"), {"id": id})

    if filename:
        try:
            blob_client = container_client.get_blob_client(filename)
            blob_client.delete_blob()
            print(f"Blob '{filename}' deleted successfully.")
        except Exception as e:
            print("⚠️ Blob deletion error:", e)

    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)
