import PIL.Image
import io
import json
from google import genai
from pydantic import BaseModel
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# 1. ĐÃ CHỈNH SỬA: Chuỗi kết nối khít 100% với SQL Server (.\SQLEXPRESS) và database (QuanLyDaoTaoAI) của bạn
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mssql+pyodbc://@localhost/SQLEXPRESS/QuanLyDaoTaoAI'
    '?driver=SQL+Server&trusted_connection=yes'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. ĐỊNH NGHĨA CẤU TRÚC BẢNG: Tự động map và sinh cột chuẩn NVARCHAR lưu tiếng Việt ổn định
class HocBa(db.Model):
    __tablename__ = 'hocba'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ho_ten = db.Column(db.NVARCHAR(255))
    ngay_thang_nam_sinh = db.Column(db.NVARCHAR(100))
    noi_sinh = db.Column(db.NVARCHAR(255))
    que_quan = db.Column(db.NVARCHAR(255))
    noi_o_hien_nay = db.Column(db.NVARCHAR(500))
    ho_va_ten_cha = db.Column(db.NVARCHAR(255))
    ho_va_ten_me = db.Column(db.NVARCHAR(255))
    lop = db.Column(db.NVARCHAR(50))
    truong = db.Column(db.NVARCHAR(255))
    khoa_hoc = db.Column(db.NVARCHAR(100))
    xep_loai = db.Column(db.NVARCHAR(100))
    hanh_kiem = db.Column(db.NVARCHAR(100))
    ghi_chu = db.Column(db.NVARCHAR(max))
    noi_dung_day_du = db.Column(db.NVARCHAR(max))
    created_at = db.Column(db.DateTime, default=datetime.now)

# API key của bạn giữ nguyên bảo mật
client = genai.Client(api_key="AIzaSyAUbUXIR7DfB5k8On4nVjAcCOzx0DgiPC0")  

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    file = request.files.get('file') or request.files.get('image')
    if not file or file.filename == '':
        return jsonify({'error': 'Khong co anh'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Dinh dang khong ho tro'}), 400

    try:
        img = PIL.Image.open(io.BytesIO(file.read()))
        prompt = """
        Đây là ảnh học bạ học sinh hoặc giấy tờ cá nhân. Hãy đọc và trích xuất toàn bộ thông tin cá nhân điền vào các trường tương ứng.
        Nếu trường nào không xuất hiện, hãy để chuỗi trống "".
        Trường 'noi_dung_day_du' phải chứa toàn bộ văn bản thô đọc được trong bức ảnh này.
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img],
            config={
                'response_mime_type': 'application/json',
                'response_schema': HocBaData,
            }
        )
        data = json.loads(response.text)
        return jsonify({'data': data})
    except Exception as e:
        return jsonify({'error': f'Loi he thong: {str(e)}'}), 500

@app.route('/save', methods=['POST'])
def save():
    d = request.json
    if not d:
        return jsonify({'error': 'Du lieu khong hop le'}), 400
        
    try:
        new_record = HocBa(
            ho_ten=d.get('ho_ten',''),
            ngay_thang_nam_sinh=d.get('ngay_thang_nam_sinh',''),
            noi_sinh=d.get('noi_sinh',''),
            que_quan=d.get('que_quan',''),
            noi_o_hien_nay=d.get('noi_o_hien_nay',''),
            ho_va_ten_cha=d.get('ho_va_ten_cha',''),
            ho_va_ten_me=d.get('ho_va_ten_me',''),
            lop=d.get('lop',''),
            truong=d.get('truong',''),
            khoa_hoc=d.get('Khoa_hoc',''),
            xep_loai=d.get('xep_loai',''),
            hanh_kiem=d.get('hanh_kiem',''),
            ghi_chu=d.get('ghi_chu',''),
            noi_dung_day_du=d.get('noi_dung_day_du','')
        )
        db.session.add(new_record)
        db.session.commit()
        return jsonify({'message': 'Da luu vao SQL Server (QuanLyDaoTaoAI) thanh cong!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Loi luu database: {str(e)}'}), 500

@app.route('/records', methods=['GET'])
def records():
    search = request.args.get('search', '')
    try:
        query = HocBa.query
        if search:
            query = query.filter(
                (HocBa.ho_ten.like(f'%{search}%')) | 
                (HocBa.lop.like(f'%{search}%')) | 
                (HocBa.truong.like(f'%{search}%'))
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
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': f'Loi tai du lieu: {str(e)}'}), 500

@app.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    try:
        record = HocBa.query.get(record_id)
        if record:
            db.session.delete(record)
            db.session.commit()
            return jsonify({'message': 'Da xoa thanh cong!'})
        return jsonify({'error': 'Khong tim thay record'}), 404
    except Exception as e:
        return jsonify({'error': f'Loi xoa record: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Lệnh tự động quét và tạo bảng chuẩn cấu trúc mới lên SQL Server
    app.run(host='0.0.0.0', port=5000, debug=True)