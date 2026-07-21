from datetime import datetime
import io
import json
import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from google import genai
import PIL.Image
from pydantic import BaseModel

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Sử dụng SQLite để chạy mượt mà trên Render (không bị lỗi pyodbc/SQL Server)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///local_data.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================
# GEMINI API CLIENT INITIALIZATION
# =========================
# SDK sẽ TỰ ĐỘNG đọc biến môi trường GEMINI_API_KEY mà bạn vừa set trên Render
client = genai.Client()


# =========================
# DATABASE MODEL
# =========================
class HocBa(db.Model):
  __tablename__ = 'hocba'

  id = db.Column(db.Integer, primary_key=True, autoincrement=True)
  ho_ten = db.Column(db.String(255))
  ngay_thang_nam_sinh = db.Column(db.String(100))
  noi_sinh = db.Column(db.String(255))
  que_quan = db.Column(db.String(255))
  noi_o_hien_nay = db.Column(db.String(500))
  ho_va_ten_cha = db.Column(db.String(255))
  ho_va_ten_me = db.Column(db.String(255))
  lop = db.Column(db.String(50))
  truong = db.Column(db.String(255))
  khoa_hoc = db.Column(db.String(100))
  xep_loai = db.Column(db.String(100))
  hanh_kiem = db.Column(db.String(100))
  ghi_chu = db.Column(db.Text)
  noi_dung_day_du = db.Column(db.Text)
  created_at = db.Column(db.DateTime, default=datetime.now)


# =========================
# RESPONSE SCHEMA
# =========================
class HocBaData(BaseModel):
  ho_ten: str
  ngay_thang_nam_sinh: str
  noi_sinh: str
  que_quan: str
  noi_o_hien_nay: str
  ho_va_ten_cha: str
  ho_va_ten_me: str
  lop: str
  truong: str
  Khoa_hoc: str
  xep_loai: str
  hanh_kiem: str
  ghi_chu: str
  noi_dung_day_du: str


# =========================
# FUNCTIONS
# =========================
def allowed_file(filename):
  return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


# =========================
# ROUTES
# =========================
@app.route('/')
def index():
  return render_template('index.html')


@app.route('/scan', methods=['POST'])
def scan():
  file = request.files.get('file') or request.files.get('image')

  if not file:
    return jsonify({'error': 'Khong co anh'}), 400
  if file.filename == '':
    return jsonify({'error': 'Ten file rong'}), 400
  if not allowed_file(file.filename):
    return jsonify({'error': 'Dinh dang khong ho tro'}), 400

 try:
        img_bytes = file.read()
        img = PIL.Image.open(io.BytesIO(img_bytes))

        prompt = """
        Đây là ảnh học bạ hoặc giấy tờ cá nhân.
        Hãy OCR và trích xuất dữ liệu theo đúng schema JSON được cung cấp.
        Nếu trường nào không xuất hiện thông tin trong ảnh thì để chuỗi rỗng "".
        Trường 'noi_dung_day_du' phải chứa toàn bộ khối văn bản thô đọc được trên ảnh.
        """

        # Thêm 4 khoảng trắng đằng trước dòng dưới này:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, img],
            config={
                'response_mime_type': 'application/json',
                'response_schema': HocBaData,
            },
        )

        data = json.loads(response.text)

        return jsonify({'success': True, 'data': data})

  except Exception as e:
    return jsonify({'success': False, 'error': f'Loi Gemini API: {str(e)}'}), 500


@app.route('/save', methods=['POST'])
def save():
  d = request.json
  if not d:
    return jsonify({'error': 'Du lieu khong hop le'}), 400

  try:
    new_record = HocBa(
        ho_ten=d.get('ho_ten', ''),
        ngay_thang_nam_sinh=d.get('ngay_thang_nam_sinh', ''),
        noi_sinh=d.get('noi_sinh', ''),
        que_quan=d.get('que_quan', ''),
        noi_o_hien_nay=d.get('noi_o_hien_nay', ''),
        ho_va_ten_cha=d.get('ho_va_ten_cha', ''),
        ho_va_ten_me=d.get('ho_va_ten_me', ''),
        lop=d.get('lop', ''),
        truong=d.get('truong', ''),
        khoa_hoc=d.get('Khoa_hoc', ''),
        xep_loai=d.get('xep_loai', ''),
        hanh_kiem=d.get('hanh_kiem', ''),
        ghi_chu=d.get('ghi_chu', ''),
        noi_dung_day_du=d.get('noi_dung_day_du', ''),
        created_at=datetime.now(),
    )
    db.session.add(new_record)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Da luu thanh cong'})
  except Exception as e:
    db.session.rollback()
    return jsonify({'success': False, 'error': f'Loi database: {str(e)}'}), 500


@app.route('/records', methods=['GET'])
def records():
  try:
    search = request.args.get('search', '')
    query = HocBa.query
    if search:
      query = query.filter(
          (HocBa.ho_ten.like(f'%{search}%'))
          | (HocBa.lop.like(f'%{search}%'))
          | (HocBa.truong.like(f'%{search}%'))
      )
    rows = query.order_by(HocBa.created_at.desc()).all()
    results = []
    for r in rows:
      results.append({
          'id': r.id,
          'ho_ten': r.ho_ten,
          'lop': r.lop,
          'truong': r.truong,
          'Khoa_hoc': r.khoa_hoc,
          'created_at': (
              r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
          ),
      })
    return jsonify(results)
  except Exception as e:
    return jsonify({'error': f'Loi tai du lieu: {str(e)}'}), 500


@app.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
  try:
    record = HocBa.query.get(record_id)
    if not record:
      return jsonify({'error': 'Khong tim thay record'}), 404
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Da xoa thanh cong'})
  except Exception as e:
    return jsonify({'error': f'Loi xoa record: {str(e)}'}), 500


# =========================
# MAIN
# =========================
if __name__ == '__main__':
  with app.app_context():
    db.create_all()
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port, debug=True)
