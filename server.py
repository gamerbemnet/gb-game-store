import os,time,bcrypt,re,secrets,json
import requests as http_requests
from flask import Flask,send_from_directory,Response,request as flask_request
from flask_socketio import SocketIO,emit

app=Flask(__name__,static_folder='public')
app.config['SECRET_KEY']=secrets.token_hex(32)

DB_PATH=os.path.join(os.path.dirname(__file__),'db.json')
USE_SB=False
json_db={}

def load_json():
    if os.path.exists(DB_PATH):
        with open(DB_PATH,'r',encoding='utf-8') as f:
            try: return json.load(f)
            except: pass
    return {'users':[],'games':[],'gameRequests':[],'downloadRequests':[],'notifications':[],'ratings':[],'chat':[],'comments':[],'reports':[],'announcements':[],'polls':[],'changelogs':[],'events':[],'faqs':[],'reviews':[],'settings':{}}

def save_json(data):
    with open(DB_PATH,'w',encoding='utf-8') as f:
        json.dump(data,f,indent=2,ensure_ascii=False,default=str)

json_db=load_json()

SB_URL=os.environ.get('SUPABASE_URL','')
SB_KEY=os.environ.get('SUPABASE_KEY','')

def sb_headers():
    return{'apikey':SB_KEY,'Authorization':f'Bearer {SB_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def sb_base():return f'{SB_URL}/rest/v1'

if SB_URL and SB_KEY:
    try:
        r=http_requests.get(f'{sb_base()}/documents',headers=sb_headers(),params={'select':'id','limit':'1'},timeout=10)
        if r.status_code==200:
            USE_SB=True
            print('Connected to Supabase')
        else:
            print(f'Supabase check failed: {r.status_code} {r.text[:200]}')
    except Exception as e:
        print(f'Supabase connection failed: {e}')
if not USE_SB:
    print('Using db.json fallback')

def sb_find_ids(col_name,query=None):
    url=f'{sb_base()}/documents'
    params={'collection':f'eq.{col_name}','select':'id,data'}
    try:
        r=http_requests.get(url,headers=sb_headers(),params=params,timeout=15)
        if r.status_code!=200:return[]
        docs=r.json()
        if query:
            docs=[d for d in docs if all(d['data'].get(k)==v for k,v in query.items())]
        return docs
    except Exception as e:
        print(f'SB find error: {e}');return[]

def db_find(col_name,query=None):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        return[d['data'] for d in docs]
    return[x for x in json_db.get(col_name,[]) if not query or all(x.get(k)==v for k,v in query.items())]

def db_find_one(col_name,query):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        return docs[0]['data'] if docs else None
    for x in json_db.get(col_name,[]):
        if all(x.get(k)==v for k,v in query.items()):return x
    return None

def db_insert(col_name,doc):
    if USE_SB:
        try:
            r=http_requests.post(f'{sb_base()}/documents',headers=sb_headers(),json={'collection':col_name,'data':doc},timeout=15)
            if r.status_code not in(200,201):print(f'SB insert error: {r.status_code} {r.text[:200]}')
        except Exception as e:print(f'SB insert error: {e}')
    else:
        if col_name not in json_db:json_db[col_name]=[]
        json_db[col_name].append(doc)
        save_json(json_db)

def db_update(col_name,query,update,set_=True,inc=None,push=None,pull=None):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        if not docs:return
        d=docs[0]
        data=d['data'].copy()
        if update and set_:data.update(update)
        if inc:
            for k,v in inc.items():data[k]=data.get(k,0)+v
        if push:
            for k,v in push.items():
                if k not in data:data[k]=[]
                if isinstance(data[k],list):data[k].append(v)
        if pull:
            for k,v in pull.items():
                if k in data and isinstance(data[k],list) and v in data[k]:data[k].remove(v)
        try:
            r=http_requests.patch(f'{sb_base()}/documents?id=eq.{d["id"]}',headers=sb_headers(),json={'data':data},timeout=15)
            if r.status_code not in(200,204):print(f'SB update error: {r.status_code}')
        except Exception as e:print(f'SB update error: {e}')
    else:
        for x in json_db.get(col_name,[]):
            if all(x.get(k)==v for k,v in query.items()):
                if update:x.update(update)
                if inc:
                    for k,v in inc.items():x[k]=x.get(k,0)+v
                if push:
                    for k,v in push.items():
                        if k not in x:x[k]=[]
                        if isinstance(x[k],list):x[k].append(v)
                if pull:
                    for k,v in pull.items():
                        if k in x and isinstance(x[k],list) and v in x[k]:x[k].remove(v)
        save_json(json_db)

def db_delete(col_name,query):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        for d in docs:
            try:http_requests.delete(f'{sb_base()}/documents?id=eq.{d["id"]}',headers=sb_headers(),timeout=15)
            except Exception as e:print(f'SB delete error: {e}')
    else:
        json_db[col_name]=[x for x in json_db.get(col_name,[]) if not all(x.get(k)==v for k,v in query.items())]
        save_json(json_db)

def db_delete_many(col_name,query):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        for d in docs:
            try:http_requests.delete(f'{sb_base()}/documents?id=eq.{d["id"]}',headers=sb_headers(),timeout=15)
            except Exception as e:print(f'SB delete error: {e}')
    else:
        json_db[col_name]=[x for x in json_db.get(col_name,[]) if not all(x.get(k)==v for k,v in query.items())]
        save_json(json_db)

def db_update_many(col_name,query,update):
    if USE_SB:
        docs=sb_find_ids(col_name,query)
        for d in docs:
            data=d['data'].copy()
            data.update(update)
            try:http_requests.patch(f'{sb_base()}/documents?id=eq.{d["id"]}',headers=sb_headers(),json={'data':data},timeout=15)
            except Exception as e:print(f'SB update_many error: {e}')
    else:
        for x in json_db.get(col_name,[]):
            if all(x.get(k)==v for k,v in query.items()):x.update(update)
        save_json(json_db)

def db_count(col_name,query=None):
    if USE_SB:
        return len(sb_find_ids(col_name,query))
    return len(db_find(col_name,query))

def db_aggregate(col_name,pipeline):
    return[]

socketio=SocketIO(app,cors_allowed_origins='*',async_mode='gevent')
online_users={}
typing_users={}

if not db_find_one('users',{'username':'owner'}):
    hashed=bcrypt.hashpw('Bemnet@2014'.encode(),bcrypt.gensalt()).decode()
    db_insert('users',{'username':'owner','password':hashed,'role':'owner','realName':'Owner','location':'Admin Office','avatar':'','bio':'','badges':[],'favorites':[],'downloadHistory':[],'joinDate':int(time.time()*1000),'lastSeen':int(time.time()*1000),'notifications':True,'soundNotif':True,'theme':'dark','accentColor':'#00f0ff','fontSize':14,'achievements':[],'socialLinks':{},'status':'online','customStatus':'','inventory':[],'coins':0,'title':''})


def get_setting(key,default=None):
    if USE_SB:
        docs=sb_find_ids('settings',{'_id':key})
        return docs[0]['data'].get('value',default) if docs else default
    return json_db.get('settings',{}).get(key,default)

def set_setting(key,value):
    if USE_SB:
        docs=sb_find_ids('settings',{'_id':key})
        if docs:
            http_requests.patch(f'{sb_base()}/documents?id=eq.{docs[0]["id"]}',headers=sb_headers(),json={'data':{'_id':key,'value':value}},timeout=15)
        else:
            db_insert('settings',{'_id':key,'value':value})
    else:
        if 'settings' not in json_db:json_db['settings']={}
        json_db['settings'][key]=value
        save_json(json_db)

@app.route('/')
def index():return send_from_directory('public','index.html')

@app.route('/ads.js')
def proxy_ads():
    try:
        r=http_requests.get('https://pl29836648.effectivecpmnetwork.com/78/c8/6f/78c86f69ec008d2f9b114aa9d0e152fe.js',timeout=20,headers={'User-Agent':flask_request.headers.get('User-Agent',''),'Referer':flask_request.headers.get('Referer','')})
        return Response(r.content,mimetype='application/javascript',headers={'Cache-Control':'public, max-age=3600','Access-Control-Allow-Origin':'*','Content-Disposition':'inline'})
    except Exception as e:
        print(f'Ad proxy failed: {e}')
        return '// ad unavailable',200

@app.route('/download/<int:game_id>')
def proxy_download(game_id):
    auth_user=flask_request.args.get('u','')
    user=db_find_one('users',{'username':auth_user})
    if not user:return 'Not logged in',403
    game=db_find_one('games',{'id':game_id})
    if not game:return 'Game not found',404
    is_admin=user.get('role') in ('admin','owner')
    is_approved=db_find_one('downloadRequests',{'game':game['name'],'user':user['username'],'status':'approved'})
    if not is_admin and not is_approved:return 'Not approved',403
    link=game.get('downloadLink','')
    if not link:return 'No link',404
    try:
        dm=re.search(r'drive\.google\.com.*?/d/([a-zA-Z0-9_-]+)',link)
        if dm:link=f'https://drive.google.com/uc?export=download&id={dm.group(1)}'
        r=http_requests.get(link,stream=True,timeout=60,allow_redirects=True)
        h=dict(r.headers);resp=Response(r.iter_content(chunk_size=8192),status=r.status_code)
        for k in ['Content-Type','Content-Length','Content-Disposition']:
            if k in h:resp.headers[k]=h[k]
        if 'Content-Disposition' not in resp.headers:resp.headers['Content-Disposition']=f'attachment; filename="{game["name"]}"'
        if user.get('role')!='owner':
            db_update('users',{'username':user['username']},push={'downloadHistory':{'game':game['name'],'time':int(time.time()*1000)}})
            db_update('games',{'id':game_id},inc={'downloads':1})
        return resp
    except Exception as e:return f'Failed: {str(e)}',500

def make_user_safe(u):
    return {k:u.get(k,'') for k in ['username','role','realName','avatar','bio','badges','favorites','downloadHistory','joinDate','lastSeen','notifications','soundNotif','theme','accentColor','fontSize','achievements','coins','title','status','customStatus','inventory']}

@socketio.on('connect')
def handle_connect():print('Connected')
@socketio.on('disconnect')
def handle_disconnect():print('Disconnected')
@socketio.on('user_online')
def handle_online(data):
    uname=data.get('username','')
    if uname:
        online_users[uname]=time.time()
        db_update('users',{'username':uname},{'lastSeen':int(time.time()*1000)})
    socketio.emit('online_count',{'count':len(online_users)})
@socketio.on('typing')
def handle_typing(data):
    uname=data.get('username','')
    if uname:
        typing_users[uname]=time.time()
        others=[u for u in typing_users if u!=uname and time.time()-typing_users[u]<3]
        socketio.emit('typing_update',{'users':others})
@socketio.on('get_db')
def handle_get_db():
    users_raw=db_find('users')
    chat_raw=db_find('chat')
    chat_raw.sort(key=lambda m:m.get('time',0),reverse=True)
    chat_raw=chat_raw[:100]
    emit('db_data',{
        'users':[make_user_safe(u) for u in users_raw],
        'games':db_find('games'),
        'gameRequests':db_find('gameRequests'),
        'downloadRequests':db_find('downloadRequests'),
        'notifications':db_find('notifications'),
        'ratings':db_find('ratings'),
        'chat':chat_raw,
        'comments':db_find('comments'),
        'reports':db_find('reports'),
        'announcements':db_find('announcements'),
        'polls':db_find('polls'),
        'changelogs':db_find('changelogs'),
        'events':db_find('events'),
        'faqs':db_find('faqs'),
        'reviews':db_find('reviews'),
        'maintenance':get_setting('maintenance',False),
        'version':get_setting('version','2.0.0')
    })
@socketio.on('signup')
def handle_signup(data):
    u=data.get('username','').strip();p=data.get('password','');rn=data.get('realName','').strip()
    if not u or not p or not rn:emit('signup_result',{'error':'Fill in all fields'});return
    if len(u)<3:emit('signup_result',{'error':'Username must be 3+ chars'});return
    if db_find_one('users',{'username':u}):emit('signup_result',{'error':'Username taken'});return
    if not re.match(r'^(?=.*[A-Za-z])(?=.*\d).{6,}$',p):emit('signup_result',{'error':'Password must be 6+ chars with letters and numbers'});return
    hashed=bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode()
    nu={'username':u,'password':hashed,'role':'user','realName':rn,'location':'','avatar':'','bio':'','badges':[],'favorites':[],'downloadHistory':[],'joinDate':int(time.time()*1000),'lastSeen':int(time.time()*1000),'notifications':True,'soundNotif':True,'theme':'dark','accentColor':'#00f0ff','fontSize':14,'achievements':['Newcomer'],'socialLinks':{},'status':'online','customStatus':'','inventory':[],'coins':10,'title':'Newcomer'}
    db_insert('users',nu)
    notif={'id':int(time.time()*1000),'to':'admin','from':u,'message':f'New user: {rn} (@{u})','read':False,'time':int(time.time()*1000),'type':'system'}
    db_insert('notifications',notif);socketio.emit('new_notification',notif)
    emit('signup_result',{'ok':True,'user':make_user_safe(nu)})
@socketio.on('signin')
def handle_signin(data):
    u=data.get('username','').strip();p=data.get('password','')
    user=db_find_one('users',{'username':u})
    if not user or not bcrypt.checkpw(p.encode(),user['password'].encode()):emit('signin_result',{'error':'Invalid credentials'});return
    db_update('users',{'username':u},{'lastSeen':int(time.time()*1000)})
    emit('signin_result',{'ok':True,'user':make_user_safe(user)})
@socketio.on('add_game')
def handle_add_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):emit('add_game_result',{'error':'No permission'});return
    name=data.get('name','').strip()
    if not name:emit('add_game_result',{'error':'Name required'});return
    if db_find_one('games',{'name':name}):emit('add_game_result',{'error':'Game exists'});return
    game={'name':name,'img':data.get('img',''),'downloadLink':data.get('downloadLink',''),'description':data.get('description',''),'category':data.get('category','Other'),'addedBy':user.get('username',''),'id':int(time.time()*1000),'downloads':0,'views':0,'size':data.get('size',''),'developer':data.get('developer',''),'releaseDate':data.get('releaseDate',''),'version':data.get('gameVersion','1.0'),'featured':False,'screenshots':data.get('screenshots',[]),'tags':data.get('tags',[]),'minReqs':data.get('minReqs',''),'maxReqs':data.get('maxReqs',''),'trailer':data.get('trailer',''),'platform':data.get('platform','PC'),'ageRating':data.get('ageRating',' Everyone'),'price':data.get('price','Free'),'dlcs':[],'changelog':[],'faq':[]}
    db_insert('games',game);socketio.emit('game_added',game);emit('add_game_result',{'ok':True})
@socketio.on('update_game')
def handle_update_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    game=db_find_one('games',{'id':data.get('id')})
    if not game:return
    update={}
    for k in ['name','img','downloadLink','description','category','size','developer','releaseDate','version','featured','screenshots','tags','minReqs','maxReqs','trailer','platform','ageRating','price']:
        if k in data:update[k]=data[k]
    if update:db_update('games',{'id':data['id']},update)
    socketio.emit('game_updated',db_find_one('games',{'id':data['id']}))
@socketio.on('delete_game')
def handle_delete_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    gid=data.get('id')
    db_delete('games',{'id':gid})
    db_delete_many('ratings',{'gameId':gid})
    db_delete_many('comments',{'gameId':gid})
    socketio.emit('game_deleted',gid)
@socketio.on('toggle_favorite')
def handle_fav(data):
    user=data.get('user');gid=data.get('gameId')
    if not user:return
    u=db_find_one('users',{'username':user['username']})
    if not u:return
    favs=u.get('favorites',[])
    if gid in favs:favs.remove(gid)
    else:favs.append(gid)
    db_update('users',{'username':user['username']},{'favorites':favs})
    emit('favorites_updated',{'favorites':favs})
@socketio.on('add_comment')
def handle_comment(data):
    user=data.get('user');gid=data.get('gameId');text=data.get('text','').strip()
    if not user or not text:return
    if text=='__view__':
        db_update('games',{'id':gid},inc={'views':1})
        return
    c={'id':int(time.time()*1000),'gameId':gid,'user':user['username'],'realName':user.get('realName',''),'role':user.get('role','user'),'text':text,'time':int(time.time()*1000),'likes':0,'likedBy':[]}
    db_insert('comments',c);socketio.emit('new_comment',c)
@socketio.on('like_comment')
def handle_like(data):
    user=data.get('user');cid=data.get('commentId')
    if not user:return
    c=db_find_one('comments',{'id':cid})
    if not c:return
    liked=c.get('likedBy',[])
    if user['username'] in liked:liked.remove(user['username']);c['likes']=max(0,c.get('likes',0)-1)
    else:liked.append(user['username']);c['likes']=c.get('likes',0)+1
    db_update('comments',{'id':cid},{'likedBy':liked,'likes':c['likes']})
    socketio.emit('comment_liked',{'commentId':cid,'likes':c['likes'],'likedBy':liked})
@socketio.on('add_review')
def handle_review(data):
    user=data.get('user');gid=data.get('gameId');title=data.get('title','').strip();text=data.get('text','').strip();rating=data.get('rating',5)
    if not user or not text:return
    rv={'id':int(time.time()*1000),'gameId':gid,'user':user['username'],'realName':user.get('realName',''),'title':title,'text':text,'rating':rating,'time':int(time.time()*1000),'helpful':0,'helpfulBy':[]}
    db_insert('reviews',rv);socketio.emit('new_review',rv)
@socketio.on('helpful_review')
def handle_helpful(data):
    user=data.get('user');rid=data.get('reviewId')
    if not user:return
    rv=db_find_one('reviews',{'id':rid})
    if not rv:return
    hb=rv.get('helpfulBy',[])
    if user['username'] in hb:hb.remove(user['username']);rv['helpful']=max(0,rv.get('helpful',0)-1)
    else:hb.append(user['username']);rv['helpful']=rv.get('helpful',0)+1
    db_update('reviews',{'id':rid},{'helpfulBy':hb,'helpful':rv['helpful']})
    socketio.emit('review_helpful',{'reviewId':rid,'helpful':rv['helpful']})
@socketio.on('rate_game')
def handle_rate(data):
    user=data.get('user');gid=data.get('gameId');rating=data.get('rating',0)
    if not user or not gid or not(1<=rating<=5):return
    db_delete_many('ratings',{'gameId':gid,'user':user['username']})
    db_insert('ratings',{'gameId':gid,'user':user['username'],'rating':rating,'time':int(time.time()*1000)})
    all_ratings=db_find('ratings',{'gameId':gid})
    if all_ratings:
        avg=round(sum(r['rating'] for r in all_ratings)/len(all_ratings),1)
        cnt=len(all_ratings)
    else:avg=0;cnt=0
    socketio.emit('rating_updated',{'gameId':gid,'avg':avg,'count':cnt})
@socketio.on('vote_poll')
def handle_poll(data):
    user=data.get('user');pid=data.get('pollId');option=data.get('option')
    if not user or not pid:return
    poll=db_find_one('polls',{'id':pid})
    if not poll:return
    voters=poll.get('voters',{})
    voters[user['username']]=option
    for o in poll['options']:o['votes']=sum(1 for v in voters.values() if v==o['text'])
    db_update('polls',{'id':pid},{'voters':voters,'options':poll['options']})
    socketio.emit('poll_updated',db_find_one('polls',{'id':pid}))
@socketio.on('create_poll')
def handle_create_poll(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    poll={'id':int(time.time()*1000),'question':data.get('question',''),'options':[{'text':o,'votes':0} for o in data.get('options',[])],'createdBy':user['username'],'time':int(time.time()*1000),'voters':{},'active':True}
    db_insert('polls',poll);socketio.emit('new_poll',poll)
@socketio.on('add_faq')
def handle_faq(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    faq={'id':int(time.time()*1000),'question':data.get('question',''),'answer':data.get('answer',''),'by':user['username']}
    db_insert('faqs',faq);socketio.emit('new_faq',faq)
@socketio.on('add_changelog')
def handle_changelog(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    cl={'id':int(time.time()*1000),'version':data.get('version',''),'changes':data.get('changes',''),'by':user['username'],'time':int(time.time()*1000)}
    db_insert('changelogs',cl);socketio.emit('new_changelog',cl)
@socketio.on('add_event')
def handle_event(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    ev={'id':int(time.time()*1000),'title':data.get('title',''),'description':data.get('description',''),'date':data.get('date',''),'reward':data.get('reward',''),'by':user['username']}
    db_insert('events',ev);socketio.emit('new_event',ev)
@socketio.on('claim_event')
def handle_claim(data):
    user=data.get('user');eid=data.get('eventId')
    if not user:return
    u=db_find_one('users',{'username':user['username']})
    if not u:return
    ev=db_find_one('events',{'id':eid})
    if not ev:return
    claimed=u.get('claimedEvents',[])
    if eid in claimed:return
    claimed.append(eid)
    reward=ev.get('reward','')
    if reward.isdigit():
        db_update('users',{'username':user['username']},{'claimedEvents':claimed},inc={'coins':int(reward)})
    elif reward:
        db_update('users',{'username':user['username']},{'claimedEvents':claimed},push={'inventory':reward})
    else:
        db_update('users',{'username':user['username']},{'claimedEvents':claimed})
    u=db_find_one('users',{'username':user['username']})
    emit('event_claimed',{'eventId':eid,'coins':u.get('coins',0),'inventory':u.get('inventory',[])})
@socketio.on('shop_buy')
def handle_shop(data):
    user=data.get('user');item=data.get('item','');price=data.get('price',0)
    if not user:return
    u=db_find_one('users',{'username':user['username']})
    if not u or u.get('coins',0)<price:emit('shop_result',{'error':'Not enough coins'});return
    db_update('users',{'username':user['username']},{},inc={'coins':-price},push={'inventory':item})
    u=db_find_one('users',{'username':user['username']})
    emit('shop_result',{'ok':True,'coins':u.get('coins',0),'inventory':u.get('inventory',[])})
@socketio.on('use_item')
def handle_use(data):
    user=data.get('user');item=data.get('item','')
    if not user:return
    u=db_find_one('users',{'username':user['username']})
    if not u:return
    inv=u.get('inventory',[])
    if item not in inv:return
    color_map={'Color: Red Name':'#ff4466','Color: Gold Name':'#ffc107','Color: Green Name':'#00cc66','Color: Blue Name':'#4488ff','Color: Purple Name':'#aa44ff','Color: Pink Name':'#ff66aa','Color: Orange Name':'#ff8800','Color: Cyan Name':'#00cccc','Color: White Name':'#ffffff','Color: Rainbow Name':'#ff00ff','Color: Rainbow 2':'#ff88ff','Color: Neon Green':'#00ff66','Color: Neon Blue':'#0088ff','Color: Neon Pink':'#ff44aa','Color: Neon Purple':'#aa00ff','Color: Neon Yellow':'#ffff00','Color: Crimson':'#dc143c','Color: Sapphire':'#0f52ba','Color: Emerald':'#50c878','Color: Amber':'#ffbf00','Color: Silver':'#c0c0c0','Color: Midnight':'#191970','Color: Obsidian':'#1a1a1a','Color: Iridescent':'#8888ff'}
    title_map={'Title: Pro Gamer':'Pro Gamer','Title: Legend':'Legend','Title: VIP':'VIP','Title: OG':'OG','Title: Noob':'Noob','Title: Beast':'Beast','Title: God':'God','Title: Legend 2':'Legend 2','Title: Pro':'Pro','Title: Master':'Master','Title: King':'King','Title: Hero':'Hero','Title: Shadow':'Shadow','Title: Storm':'Storm','Title: Phantom':'Phantom','Title: Titan':'Titan','Title: Sage':'Sage','Title: Warrior':'Warrior','Title: Dragon':'Dragon','Title: Phoenix':'Phoenix','Title: Astronaut':'Astronaut','Title: Hacker':'Hacker','Title: Royal':'Royal','Title: Ninja':'Ninja','Title: Overlord':'Overlord','Title: Conqueror':'Conqueror','Title: Immortal':'Immortal','Title: Destroyer':'Destroyer','Title: Ascended':'Ascended','Title: Eternal':'Eternal','Title: Cosmic':'Cosmic','Title: Void':'Void','Title: Chaos':'Chaos','Title: Alpha':'Alpha','Title: Omega':'Omega','Title: Prime':'Prime','Title: Savage':'Savage','Title: Demonic':'Demonic','Title: Angelic':'Angelic','Title: Frost':'Frost','Title: Blaze':'Blaze','Title: Eclipse':'Eclipse','Title: Quantum':'Quantum','Title: Neon':'Neon','Title: Cyber':'Cyber'}
    all_colors={**color_map}
    all_titles={**title_map}
    inv.remove(item)
    update={'inventory':inv}
    if item.startswith('Color:') and item in all_colors:
        update['accentColor']=all_colors[item]
    elif item.startswith('Title:') and item in all_titles:
        update['title']=all_titles[item]
    elif item.startswith('Title:'):
        update['title']=item.replace('Title: ','')
    elif item.startswith('Color:'):
        update['accentColor']='#00f0ff'
    db_update('users',{'username':user['username']},update)
    u=db_find_one('users',{'username':user['username']})
    emit('use_item_result',{'ok':True,'user':{'title':u.get('title',''),'accentColor':u.get('accentColor','#00f0ff'),'inventory':u.get('inventory',[]),'coins':u.get('coins',0)}})
@socketio.on('change_username')
def handle_change_username(data):
    user=data.get('user');new_name=data.get('newUsername','').strip()
    if not user or not new_name:return emit('change_name_result',{'error':'Enter a username'})
    if len(new_name)<3:return emit('change_name_result',{'error':'Username must be 3+ chars'})
    if new_name==user.get('username',''):return emit('change_name_result',{'error':'Same username'})
    if db_find_one('users',{'username':new_name}):return emit('change_name_result',{'error':'Username taken'})
    u=db_find_one('users',{'username':user['username']})
    if not u:return emit('change_name_result',{'error':'User not found'})
    inv=u.get('inventory',[])
    if 'Change Username' not in inv:return emit('change_name_result',{'error':'You need "Change Username" item from shop'})
    inv.remove('Change Username')
    old_name=u['username']
    db_update('users',{'username':old_name},{'username':new_name,'inventory':inv})
    socketio.emit('user_renamed',{'old':old_name,'new':new_name})
    emit('change_name_result',{'ok':True,'newUsername':new_name})
@socketio.on('change_name')
def handle_change_name(data):
    user=data.get('user');new_name=data.get('newName','').strip()
    if not user or not new_name:return emit('change_name_result',{'error':'Enter a name'})
    if len(new_name)<2:return emit('change_name_result',{'error':'Name must be 2+ chars'})
    u=db_find_one('users',{'username':user['username']})
    if not u:return emit('change_name_result',{'error':'User not found'})
    inv=u.get('inventory',[])
    if 'Change Name' not in inv:return emit('change_name_result',{'error':'You need "Change Name" item from shop'})
    inv.remove('Change Name')
    db_update('users',{'username':user['username']},{'realName':new_name,'inventory':inv})
    socketio.emit('profile_updated',{'username':user['username'],'avatar':u.get('avatar',''),'bio':u.get('bio','')})
    emit('change_name_result',{'ok':True,'newName':new_name})
@socketio.on('report')
def handle_report(data):
    user=data.get('user')
    if not user:return
    r={'id':int(time.time()*1000),'reportedBy':user['username'],'type':data.get('type',''),'target':data.get('target',''),'reason':data.get('reason',''),'time':int(time.time()*1000),'status':'pending'}
    db_insert('reports',r)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"Report: {r['reason']}",'read':False,'time':int(time.time()*1000),'type':'report'}
    db_insert('notifications',notif);socketio.emit('new_notification',notif)
@socketio.on('announcement')
def handle_announce(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    a={'id':int(time.time()*1000),'title':data.get('title',''),'message':data.get('message',''),'by':user['username'],'time':int(time.time()*1000),'pinned':data.get('pinned',False)}
    db_insert('announcements',a);socketio.emit('new_announcement',a)
@socketio.on('toggle_maintenance')
def handle_maint(data):
    user=data.get('user')
    if not user or user.get('role')!='owner':return
    current=get_setting('maintenance',False)
    set_setting('maintenance',not current)
    socketio.emit('maintenance_update',{'enabled':not current})
@socketio.on('request_download')
def handle_req_dl(data):
    user=data.get('user');game=data.get('game');loc=data.get('location','')
    if not user:emit('request_download_result',{'error':'Not logged in'});return
    if db_find_one('downloadRequests',{'game':game,'user':user['username'],'status':'pending'}):emit('request_download_result',{'error':'Already requested'});return
    req={'id':int(time.time()*1000),'game':game,'user':user['username'],'realName':user.get('realName',''),'location':loc,'status':'pending','time':int(time.time()*1000)}
    db_insert('downloadRequests',req)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"{user.get('realName',user['username'])} wants to download {game}",'read':False,'time':int(time.time()*1000),'type':'download'}
    db_insert('notifications',notif)
    socketio.emit('new_download_request',req);socketio.emit('new_notification',notif);emit('request_download_result',{'ok':True})
@socketio.on('request_game')
def handle_req_game(data):
    user=data.get('user');loc=data.get('location','')
    if not user:emit('request_game_result',{'error':'Not logged in'});return
    req={'id':int(time.time()*1000),'gameName':data.get('gameName',''),'desc':data.get('desc',''),'user':user['username'],'realName':user.get('realName',''),'location':loc,'status':'pending','img':'','time':int(time.time()*1000)}
    db_insert('gameRequests',req)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"{user.get('realName',user['username'])} wants {req['gameName']}",'read':False,'time':int(time.time()*1000),'type':'gameRequest'}
    db_insert('notifications',notif)
    socketio.emit('new_game_request',req);socketio.emit('new_notification',notif);emit('request_game_result',{'ok':True})
@socketio.on('approve_download')
def handle_approve_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=db_find_one('downloadRequests',{'id':rid})
    if not req:return
    db_update('downloadRequests',{'id':rid},{'status':'approved'})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Download approved for {req['game']}!",'read':False,'time':int(time.time()*1000),'type':'approved'}
    db_insert('notifications',notif)
    socketio.emit('download_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_download')
def handle_reject_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=db_find_one('downloadRequests',{'id':rid})
    if not req:return
    db_update('downloadRequests',{'id':rid},{'status':'rejected'})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Download rejected for {req['game']}",'read':False,'time':int(time.time()*1000),'type':'rejected'}
    db_insert('notifications',notif)
    socketio.emit('download_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('approve_game_request')
def handle_approve_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=db_find_one('gameRequests',{'id':rid})
    if not req:return
    db_update('gameRequests',{'id':rid},{'status':'approved'})
    game={'name':req['gameName'],'img':'','downloadLink':'','description':req.get('desc',''),'category':'Other','addedBy':'request','id':int(time.time()*1000),'downloads':0,'views':0,'size':'','developer':'','releaseDate':'','version':'1.0','featured':False,'screenshots':[],'tags':[],'minReqs':'','maxReqs':'','trailer':'','platform':'PC','ageRating':'Everyone','price':'Free','dlcs':[],'changelog':[],'faq':[]}
    db_insert('games',game)
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Game request {req['gameName']} approved!",'read':False,'time':int(time.time()*1000),'type':'approved'}
    db_insert('notifications',notif)
    socketio.emit('game_added',game);socketio.emit('game_request_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_game_request')
def handle_reject_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=db_find_one('gameRequests',{'id':rid})
    if not req:return
    db_update('gameRequests',{'id':rid},{'status':'rejected'})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Game request {req['gameName']} rejected",'read':False,'time':int(time.time()*1000),'type':'rejected'}
    db_insert('notifications',notif)
    socketio.emit('game_request_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('mark_read')
def handle_read(data):
    user=data.get('user')
    if not user:return
    u=db_find_one('users',{'username':user})
    if u and u.get('role') in ('admin','owner'):
        db_update_many('notifications',{'to':'admin'},{'read':True})
    db_update_many('notifications',{'to':user},{'read':True})
@socketio.on('clear_notifications')
def handle_clear_notifs(data):
    user=data.get('user')
    if not user:return
    db_delete_many('notifications',{'to':user})
@socketio.on('send_chat')
def handle_chat(data):
    user=data.get('user');msg=data.get('message','').strip()
    if not user or not msg:return
    m={'id':int(time.time()*1000),'user':user['username'],'realName':user.get('realName',''),'role':user.get('role','user'),'message':msg,'time':int(time.time()*1000),'avatar':user.get('avatar','')}
    db_insert('chat',m)
    socketio.emit('new_chat',m)
@socketio.on('update_profile')
def handle_profile(data):
    user=data.get('user')
    if not user:return
    update={}
    for k in ['avatar','bio','notifications','soundNotif','theme','accentColor','fontSize','customStatus','title']:
        if k in data:update[k]=data[k]
    if update:db_update('users',{'username':user['username']},update)
    u=db_find_one('users',{'username':user['username']})
    socketio.emit('profile_updated',{'username':u['username'],'avatar':u.get('avatar',''),'bio':u.get('bio','')})
    emit('update_profile_result',{'ok':True,'user':make_user_safe(u)})
@socketio.on('make_admin')
def handle_make_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':emit('make_admin_result',{'error':'Owner only'});return
    u=db_find_one('users',{'username':target})
    if not u:emit('make_admin_result',{'error':'Not found'});return
    if u['role']=='owner':emit('make_admin_result',{'error':'Cannot change'});return
    db_update('users',{'username':target},{'role':'admin'})
    notif={'id':int(time.time()*1000),'to':target,'from':'owner','message':'You are now an admin!','read':False,'time':int(time.time()*1000),'type':'system'}
    db_insert('notifications',notif)
    socketio.emit('user_updated',{'username':target,'role':'admin'});socketio.emit('new_notification',notif);emit('make_admin_result',{'ok':True})
@socketio.on('remove_admin')
def handle_remove_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':return
    db_update('users',{'username':target},{'role':'user'})
    socketio.emit('user_updated',{'username':target,'role':'user'})
@socketio.on('promote_to_owner')
def handle_promote_owner(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':emit('make_admin_result',{'error':'Owner only'});return
    u=db_find_one('users',{'username':target})
    if not u:emit('make_admin_result',{'error':'Not found'});return
    if u['role']=='owner':emit('make_admin_result',{'error':'Already owner'});return
    db_update('users',{'username':target},{'role':'owner'})
    notif={'id':int(time.time()*1000),'to':target,'from':'owner','message':'You are now an OWNER!','read':False,'time':int(time.time()*1000),'type':'system'}
    db_insert('notifications',notif)
    socketio.emit('user_updated',{'username':target,'role':'owner'});socketio.emit('new_notification',notif);emit('make_admin_result',{'ok':True})
@socketio.on('remove_user')
def handle_remove_user(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role') not in('owner','admin') or target=='owner':return
    db_delete('users',{'username':target})
    socketio.emit('user_removed',target)
@socketio.on('give_coins')
def handle_give_coins(data):
    user=data.get('user');target=data.get('target','');amount=data.get('amount',0)
    if not user or user.get('role') not in ('admin','owner'):return
    if not target or amount<=0:return
    u=db_find_one('users',{'username':target})
    if not u:emit('give_coins_result',{'error':'User not found'});return
    db_update('users',{'username':target},inc={'coins':amount})
    notif={'id':int(time.time()*1000),'to':target,'from':user['username'],'message':f'You received {amount} coins from {user.get("realName",user["username"])}!','read':False,'time':int(time.time()*1000),'type':'system'}
    db_insert('notifications',notif);socketio.emit('new_notification',notif)
    emit('give_coins_result',{'ok':True,'target':target,'amount':amount})
    u2=db_find_one('users',{'username':target})
    socketio.emit('user_coins_updated',{'username':target,'coins':u2.get('coins',0)})

if __name__=='__main__':
    port=int(os.environ.get('PORT',3000))
    mode='Supabase' if USE_SB else 'db.json'
    print(f'G&B GAME STORE v{get_setting("version","2.0.0")} on port {port} ({mode})')
    socketio.run(app,host='0.0.0.0',port=port,debug=False)
