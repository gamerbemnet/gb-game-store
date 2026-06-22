import json,os,time,bcrypt,re,secrets
import requests as http_requests
from flask import Flask,send_from_directory,Response,request as flask_request
from flask_socketio import SocketIO,emit
app=Flask(__name__,static_folder='public')
app.config['SECRET_KEY']=secrets.token_hex(32)
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_FILE=os.path.join(BASE_DIR,'db.json')
socketio=SocketIO(app,cors_allowed_origins='*',async_mode='gevent')
online_users={}
typing_users={}
def load_db():
    try:
        with open(DB_FILE,'r') as f:return json.load(f)
    except:
        default={"users":[{"username":"owner","password":bcrypt.hashpw("Bemnet@2014".encode(),bcrypt.gensalt()).decode(),"role":"owner","realName":"Owner","location":"Admin Office","avatar":"","bio":"","badges":[],"favorites":[],"downloadHistory":[],"joinDate":int(time.time()*1000),"lastSeen":int(time.time()*1000),"notifications":True,"soundNotif":True,"theme":"dark","accentColor":"#00f0ff","fontSize":14,"achievements":[],"socialLinks":{},"status":"online","customStatus":"","inventory":[],"coins":0,"title":""}],"games":[],"gameRequests":[],"downloadRequests":[],"notifications":[],"ratings":[],"chat":[],"comments":[],"reports":[],"announcements":[],"polls":[],"leaderboard":[],"changelogs":[],"events":[],"faqs":[],"reviews":[],"wishlist":[],"collections":[],"moderation":[],"macros":[],"presets":{},"maintenance":False,"version":"2.0.0"}
        save_db(default);return default
def save_db(db):
    with open(DB_FILE,'w') as f:json.dump(db,f,indent=2)
db=load_db()
@app.route('/')
def index():return send_from_directory('public','index.html')
@app.route('/ads.js')
def proxy_ads():
    try:
        r=http_requests.get('https://pl29836648.effectivecpmnetwork.com/78/c8/6f/78c86f69ec008d2f9b114aa9d0e152fe.js',timeout=15)
        return Response(r.content,mimetype='application/javascript',headers={'Cache-Control':'public, max-age=3600','Access-Control-Allow-Origin':'*'})
    except: return '// failed to load',500
@app.route('/download/<int:game_id>')
def proxy_download(game_id):
    auth_user=flask_request.args.get('u','')
    user=next((u for u in db['users'] if u['username']==auth_user),None)
    if not user:return 'Not logged in',403
    game=next((g for g in db['games'] if g['id']==game_id),None)
    if not game:return 'Game not found',404
    is_admin=user.get('role') in ('admin','owner')
    is_approved=any(r['game']==game['name'] and r['user']==user['username'] and r['status']=='approved' for r in db['downloadRequests'])
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
            u=next((u for u in db['users'] if u['username']==user['username']),None)
            if u:
                if 'downloadHistory' not in u:u['downloadHistory']=[]
                u['downloadHistory'].append({'game':game['name'],'time':int(time.time()*1000)})
                g=next((g for g in db['games'] if g['id']==game_id),None)
                if g:g['downloads']=g.get('downloads',0)+1
                save_db(db)
        return resp
    except Exception as e:return f'Failed: {str(e)}',500

@socketio.on('connect')
def handle_connect():print('Connected')
@socketio.on('disconnect')
def handle_disconnect():print('Disconnected')
@socketio.on('user_online')
def handle_online(data):
    uname=data.get('username','')
    if uname:
        online_users[uname]=time.time()
        u=next((u for u in db['users'] if u['username']==uname),None)
        if u:u['lastSeen']=int(time.time()*1000)
        save_db(db)
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
    emit('db_data',{'users':[{'username':u['username'],'role':u['role'],'realName':u.get('realName',''),'avatar':u.get('avatar',''),'bio':u.get('bio',''),'badges':u.get('badges',[]),'favorites':u.get('favorites',[]),'downloadHistory':u.get('downloadHistory',[]),'joinDate':u.get('joinDate',0),'lastSeen':u.get('lastSeen',0),'notifications':u.get('notifications',True),'soundNotif':u.get('soundNotif',True),'theme':u.get('theme','dark'),'accentColor':u.get('accentColor','#00f0ff'),'fontSize':u.get('fontSize',14),'achievements':u.get('achievements',[]),'coins':u.get('coins',0),'title':u.get('title',''),'status':u.get('status','online'),'customStatus':u.get('customStatus',''),'inventory':u.get('inventory',[])} for u in db['users']],'games':db['games'],'gameRequests':db['gameRequests'],'downloadRequests':db['downloadRequests'],'notifications':db['notifications'],'ratings':db['ratings'],'chat':db['chat'][-100:],'comments':db['comments'],'reports':db['reports'],'announcements':db['announcements'],'polls':db['polls'],'changelogs':db['changelogs'],'events':db['events'],'faqs':db['faqs'],'reviews':db['reviews'],'wishlist':db['wishlist'],'collections':db['collections'],'maintenance':db.get('maintenance',False),'version':db.get('version','2.0.0')})
@socketio.on('signup')
def handle_signup(data):
    u=data.get('username','').strip();p=data.get('password','');rn=data.get('realName','').strip()
    if not u or not p or not rn:emit('signup_result',{'error':'Fill in all fields'});return
    if len(u)<3:emit('signup_result',{'error':'Username must be 3+ chars'});return
    if any(x['username']==u for x in db['users']):emit('signup_result',{'error':'Username taken'});return
    hashed=bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode()
    nu={"username":u,"password":hashed,"role":"user","realName":rn,"location":"","avatar":"","bio":"","badges":[],"favorites":[],"downloadHistory":[],"joinDate":int(time.time()*1000),"lastSeen":int(time.time()*1000),"notifications":True,"soundNotif":True,"theme":"dark","accentColor":"#00f0ff","fontSize":14,"achievements":["Newcomer"],"socialLinks":{},"status":"online","customStatus":"","inventory":[],"coins":10,"title":"Newcomer"}
    db['users'].append(nu);save_db(db)
    notif={"id":int(time.time()*1000),"to":"admin","from":u,"message":f"New user: {rn} (@{u})","read":False,"time":int(time.time()*1000),"type":"system"}
    db['notifications'].append(notif);save_db(db);socketio.emit('new_notification',notif)
    emit('signup_result',{'ok':True,'user':{'username':u,'role':'user','realName':rn,'avatar':'','bio':'','badges':['Newcomer'],'favorites':[],'downloadHistory':[],'joinDate':nu['joinDate'],'lastSeen':nu['lastSeen'],'notifications':True,'soundNotif':True,'theme':'dark','accentColor':'#00f0ff','fontSize':14,'achievements':['Newcomer'],'coins':10,'title':'Newcomer','status':'online','customStatus':'','inventory':[]}})
@socketio.on('signin')
def handle_signin(data):
    u=data.get('username','').strip();p=data.get('password','')
    user=next((x for x in db['users'] if x['username']==u),None)
    if not user or not bcrypt.checkpw(p.encode(),user['password'].encode()):emit('signin_result',{'error':'Invalid credentials'});return
    user['lastSeen']=int(time.time()*1000);save_db(db)
    emit('signin_result',{'ok':True,'user':{'username':user['username'],'role':user['role'],'realName':user.get('realName',''),'avatar':user.get('avatar',''),'bio':user.get('bio',''),'badges':user.get('badges',[]),'favorites':user.get('favorites',[]),'downloadHistory':user.get('downloadHistory',[]),'joinDate':user.get('joinDate',0),'lastSeen':user.get('lastSeen',0),'notifications':user.get('notifications',True),'soundNotif':user.get('soundNotif',True),'theme':user.get('theme','dark'),'accentColor':user.get('accentColor','#00f0ff'),'fontSize':user.get('fontSize',14),'achievements':user.get('achievements',[]),'coins':user.get('coins',0),'title':user.get('title',''),'status':user.get('status','online'),'customStatus':user.get('customStatus',''),'inventory':user.get('inventory',[])}})
@socketio.on('add_game')
def handle_add_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):emit('add_game_result',{'error':'No permission'});return
    name=data.get('name','').strip()
    if not name:emit('add_game_result',{'error':'Name required'});return
    if any(g['name'].lower()==name.lower() for g in db['games']):emit('add_game_result',{'error':'Game exists'});return
    game={"name":name,"img":data.get('img',''),"downloadLink":data.get('downloadLink',''),"description":data.get('description',''),"category":data.get('category','Other'),"addedBy":user.get('username',''),"id":int(time.time()*1000),"downloads":0,"views":0,"size":data.get('size',''),"developer":data.get('developer',''),"releaseDate":data.get('releaseDate',''),"version":data.get('gameVersion','1.0'),"featured":False,"screenshots":data.get('screenshots',[]),"tags":data.get('tags',[]),"minReqs":data.get('minReqs',''),"maxReqs":data.get('maxReqs',''),"trailer":data.get('trailer',''),"platform":data.get('platform','PC'),"ageRating":data.get('ageRating',' Everyone'),"price":data.get('price','Free'),"dlcs":[],"changelog":[],"faq":[]}
    db['games'].append(game);save_db(db);socketio.emit('game_added',game);emit('add_game_result',{'ok':True})
@socketio.on('update_game')
def handle_update_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    game=next((g for g in db['games'] if g['id']==data.get('id')),None)
    if not game:return
    for k in ['name','img','downloadLink','description','category','size','developer','releaseDate','version','featured','screenshots','tags','minReqs','maxReqs','trailer','platform','ageRating','price']:
        if k in data:game[k]=data[k]
    save_db(db);socketio.emit('game_updated',game)
@socketio.on('delete_game')
def handle_delete_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    gid=data.get('id')
    db['games']=[g for g in db['games'] if g['id']!=gid]
    db['ratings']=[r for r in db['ratings'] if r['gameId']!=gid]
    db['comments']=[c for c in db['comments'] if c.get('gameId')!=gid]
    save_db(db);socketio.emit('game_deleted',gid)
@socketio.on('toggle_favorite')
def handle_fav(data):
    user=data.get('user');gid=data.get('gameId')
    if not user:return
    u=next((u for u in db['users'] if u['username']==user['username']),None)
    if not u:return
    favs=u.get('favorites',[])
    if gid in favs:favs.remove(gid)
    else:favs.append(gid)
    u['favs']=favs;u['favorites']=favs;save_db(db);emit('favorites_updated',{'favorites':favs})
@socketio.on('add_comment')
def handle_comment(data):
    user=data.get('user');gid=data.get('gameId');text=data.get('text','').strip()
    if not user or not text:return
    c={"id":int(time.time()*1000),"gameId":gid,"user":user['username'],"realName":user.get('realName',''),"role":user.get('role','user'),"text":text,"time":int(time.time()*1000),"likes":0,"likedBy":[]}
    db['comments'].append(c);save_db(db);socketio.emit('new_comment',c)
@socketio.on('like_comment')
def handle_like(data):
    user=data.get('user');cid=data.get('commentId')
    if not user:return
    c=next((c for c in db['comments'] if c['id']==cid),None)
    if not user:return
    liked=c.get('likedBy',[])
    if user['username'] in liked:liked.remove(user['username']);c['likes']=max(0,c.get('likes',0)-1)
    else:liked.append(user['username']);c['likes']=c.get('likes',0)+1
    c['likedBy']=liked;save_db(db);socketio.emit('comment_liked',{'commentId':cid,'likes':c['likes'],'likedBy':liked})
@socketio.on('add_review')
def handle_review(data):
    user=data.get('user');gid=data.get('gameId');title=data.get('title','').strip();text=data.get('text','').strip();rating=data.get('rating',5)
    if not user or not text:return
    rv={"id":int(time.time()*1000),"gameId":gid,"user":user['username'],"realName":user.get('realName',''),"title":title,"text":text,"rating":rating,"time":int(time.time()*1000),"helpful":0,"helpfulBy":[]}
    db['reviews'].append(rv);save_db(db);socketio.emit('new_review',rv)
@socketio.on('helpful_review')
def handle_helpful(data):
    user=data.get('user');rid=data.get('reviewId')
    if not user:return
    rv=next((r for r in db['reviews'] if r['id']==rid),None)
    if not rv:return
    hb=rv.get('helpfulBy',[])
    if user['username'] in hb:hb.remove(user['username']);rv['helpful']=max(0,rv.get('helpful',0)-1)
    else:hb.append(user['username']);rv['helpful']=rv.get('helpful',0)+1
    rv['helpfulBy']=hb;save_db(db);socketio.emit('review_helpful',{'reviewId':rid,'helpful':rv['helpful']})
@socketio.on('rate_game')
def handle_rate(data):
    user=data.get('user');gid=data.get('gameId');rating=data.get('rating',0)
    if not user or not gid or not(1<=rating<=5):return
    db['ratings']=[r for r in db['ratings'] if not(r['gameId']==gid and r['user']==user['username'])]
    db['ratings'].append({'gameId':gid,'user':user['username'],'rating':rating,'time':int(time.time()*1000)})
    save_db(db)
    avg=sum(r['rating'] for r in db['ratings'] if r['gameId']==gid)/max(1,len([r for r in db['ratings'] if r['gameId']==gid]))
    cnt=len([r for r in db['ratings'] if r['gameId']==gid])
    socketio.emit('rating_updated',{'gameId':gid,'avg':round(avg,1),'count':cnt})
@socketio.on('vote_poll')
def handle_poll(data):
    user=data.get('user');pid=data.get('pollId');option=data.get('option')
    if not user or not pid:return
    poll=next((p for p in db['polls'] if p['id']==pid),None)
    if not poll:return
    voters=poll.get('voters',{})
    voters[user['username']]=option;poll['voters']=voters
    for o in poll['options']:o['votes']=sum(1 for v in voters.values() if v==o['text'])
    save_db(db);socketio.emit('poll_updated',poll)
@socketio.on('create_poll')
def handle_create_poll(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    poll={"id":int(time.time()*1000),"question":data.get('question',''),"options":[{"text":o,"votes":0} for o in data.get('options',[])],"createdBy":user['username'],"time":int(time.time()*1000),"voters":{},"active":True}
    db['polls'].append(poll);save_db(db);socketio.emit('new_poll',poll)
@socketio.on('add_faq')
def handle_faq(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    faq={"id":int(time.time()*1000),"question":data.get('question',''),"answer":data.get('answer',''),"by":user['username']}
    db['faqs'].append(faq);save_db(db);socketio.emit('new_faq',faq)
@socketio.on('add_changelog')
def handle_changelog(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    cl={"id":int(time.time()*1000),"version":data.get('version',''),"changes":data.get('changes',''),"by":user['username'],"time":int(time.time()*1000)}
    db['changelogs'].append(cl);save_db(db);socketio.emit('new_changelog',cl)
@socketio.on('add_event')
def handle_event(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    ev={"id":int(time.time()*1000),"title":data.get('title',''),"description":data.get('description',''),"date":data.get('date',''),"reward":data.get('reward',''),"by":user['username']}
    db['events'].append(ev);save_db(db);socketio.emit('new_event',ev)
@socketio.on('claim_event')
def handle_claim(data):
    user=data.get('user');eid=data.get('eventId')
    if not user:return
    u=next((u for u in db['users'] if u['username']==user['username']),None)
    if not u:return
    ev=next((e for e in db['events'] if e['id']==eid),None)
    if not ev:return
    claimed=u.get('claimedEvents',[])
    if eid in claimed:return
    claimed.append(eid);u['claimedEvents']=claimed
    reward=ev.get('reward','')
    if reward.isdigit():u['coins']=u.get('coins',0)+int(reward)
    elif reward:u.get('inventory',[]).append(reward)
    save_db(db);emit('event_claimed',{'eventId':eid,'coins':u.get('coins',0),'inventory':u.get('inventory',[])})
@socketio.on('shop_buy')
def handle_shop(data):
    user=data.get('user');item=data.get('item','');price=data.get('price',0)
    if not user:return
    u=next((u for u in db['users'] if u['username']==user['username']),None)
    if not u or u.get('coins',0)<price:emit('shop_result',{'error':'Not enough coins'});return
    u['coins']=u.get('coins',0)-price;u.get('inventory',[]).append(item)
    save_db(db);emit('shop_result',{'ok':True,'coins':u['coins'],'inventory':u.get('inventory',[])})
@socketio.on('use_item')
def handle_use(data):
    user=data.get('user');item=data.get('item','')
    if not user:return
    u=next((u for u in db['users'] if u['username']==user['username']),None)
    if not u:return
    inv=u.get('inventory',[])
    if item not in inv:return
    inv.remove(item);u['inventory']=inv
    titles={"Title: Pro Gamer":"Pro Gamer","Title: Legend":"Legend","Title: VIP":"VIP","Title: OG":"OG","Color: Red Name":"#ff4466","Color: Gold Name":"#ffc107","Color: Green Name":"#00cc66"}
    if item in titles:
        val=titles[item]
        if item.startswith('Title:'):u['title']=val
        elif item.startswith('Color:'):u['accentColor']=val
    save_db(db);emit('use_item_result',{'ok':True,'user':{'title':u.get('title',''),'accentColor':u.get('accentColor','#00f0ff'),'inventory':u.get('inventory',[]),'coins':u.get('coins',0)}})
@socketio.on('report')
def handle_report(data):
    user=data.get('user')
    if not user:return
    r={"id":int(time.time()*1000),"reportedBy":user['username'],"type":data.get('type',''),"target":data.get('target',''),"reason":data.get('reason',''),"time":int(time.time()*1000),"status":"pending"}
    db['reports'].append(r);save_db(db)
    notif={"id":int(time.time()*1000),"to":"admin","from":user['username'],"message":f"Report: {r['reason']}","read":False,"time":int(time.time()*1000),"type":"report"}
    db['notifications'].append(notif);save_db(db);socketio.emit('new_notification',notif)
@socketio.on('announcement')
def handle_announce(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    a={"id":int(time.time()*1000),"title":data.get('title',''),"message":data.get('message',''),"by":user['username'],"time":int(time.time()*1000),"pinned":data.get('pinned',False)}
    db['announcements'].append(a);save_db(db);socketio.emit('new_announcement',a)
@socketio.on('toggle_maintenance')
def handle_maint(data):
    user=data.get('user')
    if not user or user.get('role')!='owner':return
    db['maintenance']=not db.get('maintenance',False);save_db(db)
    socketio.emit('maintenance_update',{'enabled':db['maintenance']})
@socketio.on('request_download')
def handle_req_dl(data):
    user=data.get('user');game=data.get('game');loc=data.get('location','')
    if not user:emit('request_download_result',{'error':'Not logged in'});return
    if any(r['game']==game and r['user']==user['username'] and r['status']=='pending' for r in db['downloadRequests']):emit('request_download_result',{'error':'Already requested'});return
    req={"id":int(time.time()*1000),"game":game,"user":user['username'],"realName":user.get('realName',''),"location":loc,"status":"pending","time":int(time.time()*1000)}
    db['downloadRequests'].append(req);save_db(db)
    notif={"id":int(time.time()*1000),"to":"admin","from":user['username'],"message":f"{user.get('realName',user['username'])} wants to download {game}","read":False,"time":int(time.time()*1000),"type":"download"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('new_download_request',req);socketio.emit('new_notification',notif);emit('request_download_result',{'ok':True})
@socketio.on('request_game')
def handle_req_game(data):
    user=data.get('user');loc=data.get('location','')
    if not user:emit('request_game_result',{'error':'Not logged in'});return
    req={"id":int(time.time()*1000),"gameName":data.get('gameName',''),"desc":data.get('desc',''),"user":user['username'],"realName":user.get('realName',''),"location":loc,"status":"pending","img":"","time":int(time.time()*1000)}
    db['gameRequests'].append(req);save_db(db)
    notif={"id":int(time.time()*1000),"to":"admin","from":user['username'],"message":f"{user.get('realName',user['username'])} wants {req['gameName']}","read":False,"time":int(time.time()*1000),"type":"gameRequest"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('new_game_request',req);socketio.emit('new_notification',notif);emit('request_game_result',{'ok':True})
@socketio.on('approve_download')
def handle_approve_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=next((r for r in db['downloadRequests'] if r['id']==rid),None)
    if not req:return
    req['status']='approved'
    notif={"id":int(time.time()*1000),"to":req['user'],"from":user['username'],"message":f"Download approved for {req['game']}!","read":False,"time":int(time.time()*1000),"type":"approved"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('download_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_download')
def handle_reject_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=next((r for r in db['downloadRequests'] if r['id']==rid),None)
    if not req:return
    req['status']='rejected'
    notif={"id":int(time.time()*1000),"to":req['user'],"from":user['username'],"message":f"Download rejected for {req['game']}","read":False,"time":int(time.time()*1000),"type":"rejected"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('download_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('approve_game_request')
def handle_approve_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=next((r for r in db['gameRequests'] if r['id']==rid),None)
    if not req:return
    req['status']='approved'
    game={"name":req['gameName'],"img":"","downloadLink":"","description":req.get('desc',''),"category":"Other","addedBy":"request","id":int(time.time()*1000),"downloads":0,"views":0,"size":"","developer":"","releaseDate":"","version":"1.0","featured":False,"screenshots":[],"tags":[],"minReqs":"","maxReqs":"","trailer":"","platform":"PC","ageRating":"Everyone","price":"Free","dlcs":[],"changelog":[],"faq":[]}
    db['games'].append(game);save_db(db)
    notif={"id":int(time.time()*1000),"to":req['user'],"from":user['username'],"message":f"Game request {req['gameName']} approved!","read":False,"time":int(time.time()*1000),"type":"approved"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('game_added',game);socketio.emit('game_request_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_game_request')
def handle_reject_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=next((r for r in db['gameRequests'] if r['id']==rid),None)
    if not req:return
    req['status']='rejected'
    notif={"id":int(time.time()*1000),"to":req['user'],"from":user['username'],"message":f"Game request {req['gameName']} rejected","read":False,"time":int(time.time()*1000),"type":"rejected"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('game_request_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('mark_read')
def handle_read(data):
    user=data.get('user')
    if not user:return
    for n in db['notifications']:
        if n['to']==user or(n['to']=='admin' and user in[u['username'] for u in db['users'] if u.get('role') in('admin','owner')]):n['read']=True
    save_db(db)
@socketio.on('clear_notifications')
def handle_clear_notifs(data):
    user=data.get('user')
    if not user:return
    db['notifications']=[n for n in db['notifications'] if n['to']!=user and not(n['to']=='admin' and user in[u['username'] for u in db['users'] if u.get('role') in('admin','owner')])]
    save_db(db)
@socketio.on('send_chat')
def handle_chat(data):
    user=data.get('user');msg=data.get('message','').strip()
    if not user or not msg:return
    m={"id":int(time.time()*1000),"user":user['username'],"realName":user.get('realName',''),"role":user.get('role','user'),"message":msg,"time":int(time.time()*1000),"avatar":user.get('avatar','')}
    db['chat'].append(m)
    if len(db['chat'])>500:db['chat']=db['chat'][-500:]
    save_db(db);socketio.emit('new_chat',m)
@socketio.on('update_profile')
def handle_profile(data):
    user=data.get('user')
    if not user:return
    u=next((u for u in db['users'] if u['username']==user['username']),None)
    if not u:return
    for k in ['avatar','bio','notifications','soundNotif','theme','accentColor','fontSize','customStatus','title']:
        if k in data:u[k]=data[k]
    save_db(db)
    socketio.emit('profile_updated',{'username':u['username'],'avatar':u.get('avatar',''),'bio':u.get('bio','')})
    emit('update_profile_result',{'ok':True,'user':{'username':u['username'],'role':u['role'],'realName':u.get('realName',''),'avatar':u.get('avatar',''),'bio':u.get('bio',''),'badges':u.get('badges',[]),'favorites':u.get('favorites',[]),'downloadHistory':u.get('downloadHistory',[]),'joinDate':u.get('joinDate',0),'lastSeen':u.get('lastSeen',0),'notifications':u.get('notifications',True),'soundNotif':u.get('soundNotif',True),'theme':u.get('theme','dark'),'accentColor':u.get('accentColor','#00f0ff'),'fontSize':u.get('fontSize',14),'achievements':u.get('achievements',[]),'coins':u.get('coins',0),'title':u.get('title',''),'status':u.get('status','online'),'customStatus':u.get('customStatus',''),'inventory':u.get('inventory',[])}})
@socketio.on('make_admin')
def handle_make_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':emit('make_admin_result',{'error':'Owner only'});return
    u=next((u for u in db['users'] if u['username']==target),None)
    if not u:emit('make_admin_result',{'error':'Not found'});return
    if u['role']=='owner':emit('make_admin_result',{'error':'Cannot change'});return
    u['role']='admin';save_db(db)
    notif={"id":int(time.time()*1000),"to":target,"from":"owner","message":"You are now an admin!","read":False,"time":int(time.time()*1000),"type":"system"}
    db['notifications'].append(notif);save_db(db)
    socketio.emit('user_updated',{'username':target,'role':'admin'});socketio.emit('new_notification',notif);emit('make_admin_result',{'ok':True})
@socketio.on('remove_admin')
def handle_remove_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':return
    u=next((u for u in db['users'] if u['username']==target),None)
    if u:u['role']='user';save_db(db);socketio.emit('user_updated',{'username':target,'role':'user'})
@socketio.on('remove_user')
def handle_remove_user(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role') not in('owner','admin') or target=='owner':return
    db['users']=[u for u in db['users'] if u['username']!=target];save_db(db);socketio.emit('user_removed',target)
if __name__=='__main__':
    port=int(os.environ.get('PORT',3000))
    print(f'G&B GAME STORE v{db.get("version","2.0.0")} on port {port}')
    socketio.run(app,host='0.0.0.0',port=port,debug=False)
