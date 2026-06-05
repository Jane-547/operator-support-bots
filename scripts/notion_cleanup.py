import os, requests, time

t = os.environ['NOTION_TOKEN']
h = {'Authorization': f'Bearer {t}', 'Notion-Version': '2022-06-28'}

pages = [
    '35b57cb0-1e34-8133-b809-c689296a15f8',  # root
    '35b57cb0-1e34-8167-ac49-ccafebd19633',  # module 1
    '35b57cb0-1e34-8162-959e-f9d89e108fd9',  # module 2
    '35b57cb0-1e34-814b-9f7d-c116533738ea',  # module 3
    '35b57cb0-1e34-81d5-8dc6-f402a39eb035',  # practical exercises m3
]

deleted = 0
for pid in pages:
    r = requests.get(f'https://api.notion.com/v1/blocks/{pid}/children?page_size=100', headers=h)
    blocks = r.json().get('results', [])
    for b in blocks:
        btype = b['type']
        if btype in ('link_to_page', 'callout'):
            bid = b['id']
            dr = requests.delete(f'https://api.notion.com/v1/blocks/{bid}', headers=h)
            print(f'  deleted [{btype}] from {pid[:8]} -> {dr.status_code}')
            deleted += 1
            time.sleep(0.2)

print(f'Done: {deleted} blocks deleted')
