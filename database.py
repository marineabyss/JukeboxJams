import requests as re
import config
import os
from urllib import parse
import psycopg2

conn = config.conn
parse.uses_netloc.append("postgres")
url = parse.urlparse(os.environ["DATABASE_URL"])

def getbykeyword(keyword):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    syns = re.get('https://api.datamuse.com/words?ml=' + keyword + '&max=20').json()
    if (len(syns) != 0 and 'score' in syns[0]):
        max = syns[0]['score']
    else: max = 0
    added_word = {'word': keyword.lower(), 'score': max + 100}
    syns.append(added_word)
    syn_list = ([d['word'] for d in syns])
    scores_list = {d['word']: d['score'] for d in syns if 'score' in d}
    sql = """
    WITH query AS (SELECT unnest(%s) AS search),
    check_tags AS (SELECT id, search
    FROM query CROSS JOIN (SELECT unnest(main.playlist.tags) AS tags, id 
                            FROM main.playlist) AS tag WHERE tag.tags LIKE '%%' || search || '%%'),
    check_names AS(SELECT id, search
    FROM query CROSS JOIN (SELECT  name, id 
                            FROM main.playlist) AS tag WHERE lower(name) LIKE '%%' || search || '%%'),
    res AS (SELECT * FROM check_tags  UNION SELECT * FROM check_names)
        SELECT grouped.id, name, tracklist, tags, user_id, img, hits FROM
        (SELECT res.id, array_agg(search) as hits FROM res GROUP BY res.id) AS grouped INNER JOIN main.playlist as p ON grouped.id = p.id
    ;"""
    cur.execute(sql, ((syn_list),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    coeffs = [sum([scores_list[x] for x in row[6]]) / max for row in rows]
    sorted_list = sorted(list(zip(rows, coeffs)), key=lambda x: float(x[1]), reverse=True)
    return sorted_list


def get_playlist_image(playlist_id, user_id):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT img FROM main.playlist WHERE user_id = %s AND id = %s;
            """, (user_id,playlist_id))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[0][0]

def get_playlist(playlist_id):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, tracklist, tags, user_id, img, img_hist  FROM main.playlist WHERE id = %s;
            """, (playlist_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_color_histograms():
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
            SELECT id, img_hist FROM main.playlist;
                """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def addtofavorite(playlist_key, user_id):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
            SELECT * FROM main.favorites WHERE user_id = %s AND playlist_id = %s
        """, (user_id, playlist_key))
    rows = cur.fetchall()
    if (len(rows) == 0):
        cur.execute("""
            INSERT INTO main.favorites (user_id, playlist_id)
            VALUES (%s, %s)
        """, (user_id, playlist_key))
        conn.commit()
        res_msg = 'Плейлист добавлен в избранное'
    else:
        res_msg = 'Плейлист уже находится в избранном'
    cur.close()
    conn.close()
    return res_msg

def removefromfavorite(playlist_key, user_id):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM main.favorites WHERE user_id = %s AND playlist_id = %s
    """, (user_id, playlist_key))
    conn.commit()
    res_msg = 'Плейлист уделен из избранного'
    cur.close()
    conn.close()
    return res_msg

def getfavorites(user_id):
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    cur = conn.cursor()
    cur.execute("""
                SELECT mp.* FROM (SELECT playlist_id FROM main.favorites WHERE user_id = %s) AS up 
                INNER JOIN main.playlist AS mp ON up.playlist_id=mp.id;
            """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
