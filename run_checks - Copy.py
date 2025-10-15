from app import app

def run_checks():
    print('Creating test client...')
    client = app.test_client()

    print('GET /')
    r = client.get('/')
    print(' / ->', r.status_code)

    print('GET /login')
    r = client.get('/login')
    print(' /login ->', r.status_code)

    print('GET /all_students')
    r = client.get('/all_students')
    print(' /all_students ->', r.status_code)

    print('POST /scan_barcode (no data)')
    r = client.post('/scan_barcode', json={})
    print(' /scan_barcode ->', r.status_code, r.get_json())

if __name__ == '__main__':
    run_checks()
