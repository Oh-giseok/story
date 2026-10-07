import sqlite3
import os

db_path = os.path.join('instance', 'story.db')
if not os.path.exists(db_path):
    db_path = 'story.db'

print(f"대상 데이터베이스 경로: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 데이터베이스 내의 모든 테이블과 컬럼 정보를 조회하여 '000000' 값이 있는 경우 NULL로 업데이트
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for (table_name,) in tables:
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    for col in columns:
        col_name = col[1]
        col_type = col[2].upper()
        # DATETIME, DATE, TEXT 등 날짜나 문자열이 들어갈 수 있는 컬럼 대상 정돈
        if 'DATE' in col_type or 'TIME' in col_type or 'CHAR' in col_type or 'TEXT' in col_type:
            try:
                cursor.execute(f"UPDATE {table_name} SET {col_name} = NULL WHERE {col_name} = '000000'")
                if cursor.rowcount > 0:
                    print(f"테이블 '{table_name}'의 컬럼 '{col_name}'에서 '000000' 값 {cursor.rowcount개}개를 NULL로 변경했습니다.")
            except Exception as e:
                pass

conn.commit()
conn.close()
print("모든 데이터베이스 정리가 완료되었습니다. 이제 플라스크 서버를 다시 실행해 보세요!")