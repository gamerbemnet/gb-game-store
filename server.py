import os,time,bcrypt,re,secrets
import requests as http_requests
from flask import Flask,send_from_directory,Response,request as flask_request
from flask_socketio import SocketIO,emit
from pymongo import MongoClient

app=Flask(__name__,static_folder='public')
app.config['SECRET_KEY']=secrets.token_hex(32)

MONGO_URI=os.environ.get('MONGO_URI','mongodb+srv://imbemnet:Bemnet%402014@cluster0.ywyosex.mongodb.net/?appName=Cluster0')
client=MongoClient(MONGO_URI)
db=client['gb_game_store']

users_col=db['users']
games_col=db['games']
requests_col=db['downloadRequests']
game_requests_col=db['gameRequests']
notifications_col=db['notifications']
ratings_col=db['ratings']
chat_col=db['chat']
comments_col=db['comments']
reports_col=db['reports']
announcements_col=db['announcements']
polls_col=db['polls']
changelogs_col=db['changelogs']
events_col=db['events']
faqs_col=db['faqs']
reviews_col=db['reviews']
settings_col=db['settings']

socketio=SocketIO(app,cors_allowed_origins='*',async_mode='gevent')
online_users={}
typing_users={}

if not users_col.find_one({'username':'owner'}):
    hashed=bcrypt.hashpw('Bemnet@2014'.encode(),bcrypt.gensalt()).decode()
    users_col.insert_one({'username':'owner','password':hashed,'role':'owner','realName':'Owner','location':'Admin Office','avatar':'','bio':'','badges':[],'favorites':[],'downloadHistory':[],'joinDate':int(time.time()*1000),'lastSeen':int(time.time()*1000),'notifications':True,'soundNotif':True,'theme':'dark','accentColor':'#00f0ff','fontSize':14,'achievements':[],'socialLinks':{},'status':'online','customStatus':'','inventory':[],'coins':0,'title':''})

def get_setting(key,default=None):
    s=settings_col.find_one({'_id':key})
    return s['value'] if s else default

def set_setting(key,value):
    settings_col.update_one({'_id':key},{'$set':{'value':value}},upsert=True)

@app.route('/')
def index():return send_from_directory('public','index.html')

@app.route('/ads.js')
def proxy_ads():
    try:
        r=http_requests.get('https://pl29836648.effectivecpmnetwork.com/78/c8/6f/78c86f69ec008d2f9b114aa9d0e152fe.js',timeout=15)
        return Response(r.content,mimetype='application/javascript',headers={'Cache-Control':'public, max-age=3600','Access-Control-Allow-Origin':'*','Content-Disposition':'inline'})
    except: return '// failed to load',500

@app.route('/download/<int:game_id>')
def proxy_download(game_id):
    auth_user=flask_request.args.get('u','')
    user=users_col.find_one({'username':auth_user})
    if not user:return 'Not logged in',403
    game=games_col.find_one({'id':game_id})
    if not game:return 'Game not found',404
    is_admin=user.get('role') in ('admin','owner')
    is_approved=requests_col.find_one({'game':game['name'],'user':user['username'],'status':'approved'})
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
            users_col.update_one({'username':user['username']},{'$push':{'downloadHistory':{'game':game['name'],'time':int(time.time()*1000)}}})
            games_col.update_one({'id':game_id},{'$inc':{'downloads':1}})
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
        users_col.update_one({'username':uname},{'$set':{'lastSeen':int(time.time()*1000)}})
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
    emit('db_data',{
        'users':[make_user_safe(u) for u in users_col.find()],
        'games':list(games_col.find({},{'_id':0})),
        'gameRequests':list(game_requests_col.find({},{'_id':0})),
        'downloadRequests':list(requests_col.find({},{'_id':0})),
        'notifications':list(notifications_col.find({},{'_id':0})),
        'ratings':list(ratings_col.find({},{'_id':0})),
        'chat':[{k:v for k,v in m.items() if k!='_id'} for m in chat_col.find().sort('_id',-1).limit(100)],
        'comments':list(comments_col.find({},{'_id':0})),
        'reports':list(reports_col.find({},{'_id':0})),
        'announcements':list(announcements_col.find({},{'_id':0})),
        'polls':list(polls_col.find({},{'_id':0})),
        'changelogs':list(changelogs_col.find({},{'_id':0})),
        'events':list(events_col.find({},{'_id':0})),
        'faqs':list(faqs_col.find({},{'_id':0})),
        'reviews':list(reviews_col.find({},{'_id':0})),
        'maintenance':get_setting('maintenance',False),
        'version':get_setting('version','2.0.0')
    })
@socketio.on('signup')
def handle_signup(data):
    u=data.get('username','').strip();p=data.get('password','');rn=data.get('realName','').strip()
    if not u or not p or not rn:emit('signup_result',{'error':'Fill in all fields'});return
    if len(u)<3:emit('signup_result',{'error':'Username must be 3+ chars'});return
    if users_col.find_one({'username':u}):emit('signup_result',{'error':'Username taken'});return
    hashed=bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode()
    nu={'username':u,'password':hashed,'role':'user','realName':rn,'location':'','avatar':'','bio':'','badges':[],'favorites':[],'downloadHistory':[],'joinDate':int(time.time()*1000),'lastSeen':int(time.time()*1000),'notifications':True,'soundNotif':True,'theme':'dark','accentColor':'#00f0ff','fontSize':14,'achievements':['Newcomer'],'socialLinks':{},'status':'online','customStatus':'','inventory':[],'coins':10,'title':'Newcomer'}
    users_col.insert_one(nu)
    notif={'id':int(time.time()*1000),'to':'admin','from':u,'message':f'New user: {rn} (@{u})','read':False,'time':int(time.time()*1000),'type':'system'}
    notifications_col.insert_one(notif);socketio.emit('new_notification',notif)
    emit('signup_result',{'ok':True,'user':make_user_safe(nu)})
@socketio.on('signin')
def handle_signin(data):
    u=data.get('username','').strip();p=data.get('password','')
    user=users_col.find_one({'username':u})
    if not user or not bcrypt.checkpw(p.encode(),user['password'].encode()):emit('signin_result',{'error':'Invalid credentials'});return
    users_col.update_one({'username':u},{'$set':{'lastSeen':int(time.time()*1000)}})
    emit('signin_result',{'ok':True,'user':make_user_safe(user)})
@socketio.on('add_game')
def handle_add_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):emit('add_game_result',{'error':'No permission'});return
    name=data.get('name','').strip()
    if not name:emit('add_game_result',{'error':'Name required'});return
    if games_col.find_one({'name':name}):emit('add_game_result',{'error':'Game exists'});return
    game={'name':name,'img':data.get('img',''),'downloadLink':data.get('downloadLink',''),'description':data.get('description',''),'category':data.get('category','Other'),'addedBy':user.get('username',''),'id':int(time.time()*1000),'downloads':0,'views':0,'size':data.get('size',''),'developer':data.get('developer',''),'releaseDate':data.get('releaseDate',''),'version':data.get('gameVersion','1.0'),'featured':False,'screenshots':data.get('screenshots',[]),'tags':data.get('tags',[]),'minReqs':data.get('minReqs',''),'maxReqs':data.get('maxReqs',''),'trailer':data.get('trailer',''),'platform':data.get('platform','PC'),'ageRating':data.get('ageRating',' Everyone'),'price':data.get('price','Free'),'dlcs':[],'changelog':[],'faq':[]}
    games_col.insert_one(game);socketio.emit('game_added',game);emit('add_game_result',{'ok':True})
@socketio.on('update_game')
def handle_update_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    game=games_col.find_one({'id':data.get('id')})
    if not game:return
    update={}
    for k in ['name','img','downloadLink','description','category','size','developer','releaseDate','version','featured','screenshots','tags','minReqs','maxReqs','trailer','platform','ageRating','price']:
        if k in data:update[k]=data[k]
    if update:games_col.update_one({'id':data['id']},{'$set':update})
    socketio.emit('game_updated',games_col.find_one({'id':data['id']},{'_id':0}))
@socketio.on('delete_game')
def handle_delete_game(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    gid=data.get('id')
    games_col.delete_one({'id':gid})
    ratings_col.delete_many({'gameId':gid})
    comments_col.delete_many({'gameId':gid})
    socketio.emit('game_deleted',gid)
@socketio.on('toggle_favorite')
def handle_fav(data):
    user=data.get('user');gid=data.get('gameId')
    if not user:return
    u=users_col.find_one({'username':user['username']})
    if not u:return
    favs=u.get('favorites',[])
    if gid in favs:favs.remove(gid)
    else:favs.append(gid)
    users_col.update_one({'username':user['username']},{'$set':{'favorites':favs}})
    emit('favorites_updated',{'favorites':favs})
@socketio.on('add_comment')
def handle_comment(data):
    user=data.get('user');gid=data.get('gameId');text=data.get('text','').strip()
    if not user or not text:return
    c={'id':int(time.time()*1000),'gameId':gid,'user':user['username'],'realName':user.get('realName',''),'role':user.get('role','user'),'text':text,'time':int(time.time()*1000),'likes':0,'likedBy':[]}
    comments_col.insert_one(c);socketio.emit('new_comment',c)
@socketio.on('like_comment')
def handle_like(data):
    user=data.get('user');cid=data.get('commentId')
    if not user:return
    c=comments_col.find_one({'id':cid})
    if not user:return
    liked=c.get('likedBy',[])
    if user['username'] in liked:liked.remove(user['username']);c['likes']=max(0,c.get('likes',0)-1)
    else:liked.append(user['username']);c['likes']=c.get('likes',0)+1
    comments_col.update_one({'id':cid},{'$set':{'likedBy':liked,'likes':c['likes']}})
    socketio.emit('comment_liked',{'commentId':cid,'likes':c['likes'],'likedBy':liked})
@socketio.on('add_review')
def handle_review(data):
    user=data.get('user');gid=data.get('gameId');title=data.get('title','').strip();text=data.get('text','').strip();rating=data.get('rating',5)
    if not user or not text:return
    rv={'id':int(time.time()*1000),'gameId':gid,'user':user['username'],'realName':user.get('realName',''),'title':title,'text':text,'rating':rating,'time':int(time.time()*1000),'helpful':0,'helpfulBy':[]}
    reviews_col.insert_one(rv);socketio.emit('new_review',rv)
@socketio.on('helpful_review')
def handle_helpful(data):
    user=data.get('user');rid=data.get('reviewId')
    if not user:return
    rv=reviews_col.find_one({'id':rid})
    if not rv:return
    hb=rv.get('helpfulBy',[])
    if user['username'] in hb:hb.remove(user['username']);rv['helpful']=max(0,rv.get('helpful',0)-1)
    else:hb.append(user['username']);rv['helpful']=rv.get('helpful',0)+1
    reviews_col.update_one({'id':rid},{'$set':{'helpfulBy':hb,'helpful':rv['helpful']}})
    socketio.emit('review_helpful',{'reviewId':rid,'helpful':rv['helpful']})
@socketio.on('rate_game')
def handle_rate(data):
    user=data.get('user');gid=data.get('gameId');rating=data.get('rating',0)
    if not user or not gid or not(1<=rating<=5):return
    ratings_col.delete_many({'gameId':gid,'user':user['username']})
    ratings_col.insert_one({'gameId':gid,'user':user['username'],'rating':rating,'time':int(time.time()*1000)})
    pipeline=[{'$match':{'gameId':gid}},{'$group':{'_id':None,'avg':{'$avg':'$rating'},'count':{'$sum':1}}}]
    result=list(ratings_col.aggregate(pipeline))
    avg=round(result[0]['avg'],1) if result else 0
    cnt=result[0]['count'] if result else 0
    socketio.emit('rating_updated',{'gameId':gid,'avg':avg,'count':cnt})
@socketio.on('vote_poll')
def handle_poll(data):
    user=data.get('user');pid=data.get('pollId');option=data.get('option')
    if not user or not pid:return
    poll=polls_col.find_one({'id':pid})
    if not poll:return
    voters=poll.get('voters',{})
    voters[user['username']]=option
    for o in poll['options']:o['votes']=sum(1 for v in voters.values() if v==o['text'])
    polls_col.update_one({'id':pid},{'$set':{'voters':voters,'options':poll['options']}})
    socketio.emit('poll_updated',polls_col.find_one({'id':pid},{'_id':0}))
@socketio.on('create_poll')
def handle_create_poll(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    poll={'id':int(time.time()*1000),'question':data.get('question',''),'options':[{'text':o,'votes':0} for o in data.get('options',[])],'createdBy':user['username'],'time':int(time.time()*1000),'voters':{},'active':True}
    polls_col.insert_one(poll);socketio.emit('new_poll',poll)
@socketio.on('add_faq')
def handle_faq(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    faq={'id':int(time.time()*1000),'question':data.get('question',''),'answer':data.get('answer',''),'by':user['username']}
    faqs_col.insert_one(faq);socketio.emit('new_faq',faq)
@socketio.on('add_changelog')
def handle_changelog(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    cl={'id':int(time.time()*1000),'version':data.get('version',''),'changes':data.get('changes',''),'by':user['username'],'time':int(time.time()*1000)}
    changelogs_col.insert_one(cl);socketio.emit('new_changelog',cl)
@socketio.on('add_event')
def handle_event(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    ev={'id':int(time.time()*1000),'title':data.get('title',''),'description':data.get('description',''),'date':data.get('date',''),'reward':data.get('reward',''),'by':user['username']}
    events_col.insert_one(ev);socketio.emit('new_event',ev)
@socketio.on('claim_event')
def handle_claim(data):
    user=data.get('user');eid=data.get('eventId')
    if not user:return
    u=users_col.find_one({'username':user['username']})
    if not u:return
    ev=events_col.find_one({'id':eid})
    if not ev:return
    claimed=u.get('claimedEvents',[])
    if eid in claimed:return
    claimed.append(eid)
    reward=ev.get('reward','')
    if reward.isdigit():
        users_col.update_one({'username':user['username']},{'$set':{'claimedEvents':claimed},'$inc':{'coins':int(reward)}})
    elif reward:
        users_col.update_one({'username':user['username']},{'$set':{'claimedEvents':claimed},'$push':{'inventory':reward}})
    else:
        users_col.update_one({'username':user['username']},{'$set':{'claimedEvents':claimed}})
    u=users_col.find_one({'username':user['username']})
    emit('event_claimed',{'eventId':eid,'coins':u.get('coins',0),'inventory':u.get('inventory',[])})
@socketio.on('shop_buy')
def handle_shop(data):
    user=data.get('user');item=data.get('item','');price=data.get('price',0)
    if not user:return
    u=users_col.find_one({'username':user['username']})
    if not u or u.get('coins',0)<price:emit('shop_result',{'error':'Not enough coins'});return
    users_col.update_one({'username':user['username']},{'$inc':{'coins':-price},'$push':{'inventory':item}})
    u=users_col.find_one({'username':user['username']})
    emit('shop_result',{'ok':True,'coins':u.get('coins',0),'inventory':u.get('inventory',[])})
@socketio.on('use_item')
def handle_use(data):
    user=data.get('user');item=data.get('item','')
    if not user:return
    u=users_col.find_one({'username':user['username']})
    if not u:return
    inv=u.get('inventory',[])
    if item not in inv:return
    inv.remove(item)
    titles={'Title: Pro Gamer':'Pro Gamer','Title: Legend':'Legend','Title: VIP':'VIP','Title: OG':'OG','Color: Red Name':'#ff4466','Color: Gold Name':'#ffc107','Color: Green Name':'#00cc66'}
    update={'inventory':inv}
    if item in titles:
        val=titles[item]
        if item.startswith('Title:'):update['title']=val
        elif item.startswith('Color:'):update['accentColor']=val
    users_col.update_one({'username':user['username']},{'$set':update})
    u=users_col.find_one({'username':user['username']})
    emit('use_item_result',{'ok':True,'user':{'title':u.get('title',''),'accentColor':u.get('accentColor','#00f0ff'),'inventory':u.get('inventory',[]),'coins':u.get('coins',0)}})
@socketio.on('report')
def handle_report(data):
    user=data.get('user')
    if not user:return
    r={'id':int(time.time()*1000),'reportedBy':user['username'],'type':data.get('type',''),'target':data.get('target',''),'reason':data.get('reason',''),'time':int(time.time()*1000),'status':'pending'}
    reports_col.insert_one(r)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"Report: {r['reason']}",'read':False,'time':int(time.time()*1000),'type':'report'}
    notifications_col.insert_one(notif);socketio.emit('new_notification',notif)
@socketio.on('announcement')
def handle_announce(data):
    user=data.get('user')
    if not user or user.get('role') not in ('admin','owner'):return
    a={'id':int(time.time()*1000),'title':data.get('title',''),'message':data.get('message',''),'by':user['username'],'time':int(time.time()*1000),'pinned':data.get('pinned',False)}
    announcements_col.insert_one(a);socketio.emit('new_announcement',a)
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
    if requests_col.find_one({'game':game,'user':user['username'],'status':'pending'}):emit('request_download_result',{'error':'Already requested'});return
    req={'id':int(time.time()*1000),'game':game,'user':user['username'],'realName':user.get('realName',''),'location':loc,'status':'pending','time':int(time.time()*1000)}
    requests_col.insert_one(req)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"{user.get('realName',user['username'])} wants to download {game}",'read':False,'time':int(time.time()*1000),'type':'download'}
    notifications_col.insert_one(notif)
    socketio.emit('new_download_request',req);socketio.emit('new_notification',notif);emit('request_download_result',{'ok':True})
@socketio.on('request_game')
def handle_req_game(data):
    user=data.get('user');loc=data.get('location','')
    if not user:emit('request_game_result',{'error':'Not logged in'});return
    req={'id':int(time.time()*1000),'gameName':data.get('gameName',''),'desc':data.get('desc',''),'user':user['username'],'realName':user.get('realName',''),'location':loc,'status':'pending','img':'','time':int(time.time()*1000)}
    game_requests_col.insert_one(req)
    notif={'id':int(time.time()*1000),'to':'admin','from':user['username'],'message':f"{user.get('realName',user['username'])} wants {req['gameName']}",'read':False,'time':int(time.time()*1000),'type':'gameRequest'}
    notifications_col.insert_one(notif)
    socketio.emit('new_game_request',req);socketio.emit('new_notification',notif);emit('request_game_result',{'ok':True})
@socketio.on('approve_download')
def handle_approve_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=requests_col.find_one({'id':rid})
    if not req:return
    requests_col.update_one({'id':rid},{'$set':{'status':'approved'}})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Download approved for {req['game']}!",'read':False,'time':int(time.time()*1000),'type':'approved'}
    notifications_col.insert_one(notif)
    socketio.emit('download_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_download')
def handle_reject_dl(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=requests_col.find_one({'id':rid})
    if not req:return
    requests_col.update_one({'id':rid},{'$set':{'status':'rejected'}})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Download rejected for {req['game']}",'read':False,'time':int(time.time()*1000),'type':'rejected'}
    notifications_col.insert_one(notif)
    socketio.emit('download_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('approve_game_request')
def handle_approve_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=game_requests_col.find_one({'id':rid})
    if not req:return
    game_requests_col.update_one({'id':rid},{'$set':{'status':'approved'}})
    game={'name':req['gameName'],'img':'','downloadLink':'','description':req.get('desc',''),'category':'Other','addedBy':'request','id':int(time.time()*1000),'downloads':0,'views':0,'size':'','developer':'','releaseDate':'','version':'1.0','featured':False,'screenshots':[],'tags':[],'minReqs':'','maxReqs':'','trailer':'','platform':'PC','ageRating':'Everyone','price':'Free','dlcs':[],'changelog':[],'faq':[]}
    games_col.insert_one(game)
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Game request {req['gameName']} approved!",'read':False,'time':int(time.time()*1000),'type':'approved'}
    notifications_col.insert_one(notif)
    socketio.emit('game_added',game);socketio.emit('game_request_updated',{'id':rid,'status':'approved'});socketio.emit('new_notification',notif)
@socketio.on('reject_game_request')
def handle_reject_gr(data):
    user=data.get('user');rid=data.get('id')
    if not user or user.get('role') not in ('admin','owner'):return
    req=game_requests_col.find_one({'id':rid})
    if not req:return
    game_requests_col.update_one({'id':rid},{'$set':{'status':'rejected'}})
    notif={'id':int(time.time()*1000),'to':req['user'],'from':user['username'],'message':f"Game request {req['gameName']} rejected",'read':False,'time':int(time.time()*1000),'type':'rejected'}
    notifications_col.insert_one(notif)
    socketio.emit('game_request_updated',{'id':rid,'status':'rejected'});socketio.emit('new_notification',notif)
@socketio.on('mark_read')
def handle_read(data):
    user=data.get('user')
    if not user:return
    notifications_col.update_many({'to':user},{'$set':{'read':True}})
    if user in [u['username'] for u in users_col.find({'role':{'$in':['admin','owner']}})]:
        notifications_col.update_many({'to':'admin'},{'$set':{'read':True}})
@socketio.on('clear_notifications')
def handle_clear_notifs(data):
    user=data.get('user')
    if not user:return
    notifications_col.delete_many({'to':user})
@socketio.on('send_chat')
def handle_chat(data):
    user=data.get('user');msg=data.get('message','').strip()
    if not user or not msg:return
    m={'id':int(time.time()*1000),'user':user['username'],'realName':user.get('realName',''),'role':user.get('role','user'),'message':msg,'time':int(time.time()*1000),'avatar':user.get('avatar','')}
    chat_col.insert_one(m)
    socketio.emit('new_chat',m)
@socketio.on('update_profile')
def handle_profile(data):
    user=data.get('user')
    if not user:return
    update={}
    for k in ['avatar','bio','notifications','soundNotif','theme','accentColor','fontSize','customStatus','title']:
        if k in data:update[k]=data[k]
    if update:users_col.update_one({'username':user['username']},{'$set':update})
    u=users_col.find_one({'username':user['username']})
    socketio.emit('profile_updated',{'username':u['username'],'avatar':u.get('avatar',''),'bio':u.get('bio','')})
    emit('update_profile_result',{'ok':True,'user':make_user_safe(u)})
@socketio.on('make_admin')
def handle_make_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':emit('make_admin_result',{'error':'Owner only'});return
    u=users_col.find_one({'username':target})
    if not u:emit('make_admin_result',{'error':'Not found'});return
    if u['role']=='owner':emit('make_admin_result',{'error':'Cannot change'});return
    users_col.update_one({'username':target},{'$set':{'role':'admin'}})
    notif={'id':int(time.time()*1000),'to':target,'from':'owner','message':'You are now an admin!','read':False,'time':int(time.time()*1000),'type':'system'}
    notifications_col.insert_one(notif)
    socketio.emit('user_updated',{'username':target,'role':'admin'});socketio.emit('new_notification',notif);emit('make_admin_result',{'ok':True})
@socketio.on('remove_admin')
def handle_remove_admin(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role')!='owner':return
    users_col.update_one({'username':target},{'$set':{'role':'user'}})
    socketio.emit('user_updated',{'username':target,'role':'user'})
@socketio.on('remove_user')
def handle_remove_user(data):
    user=data.get('user');target=data.get('target','')
    if not user or user.get('role') not in('owner','admin') or target=='owner':return
    users_col.delete_one({'username':target})
    socketio.emit('user_removed',target)

if __name__=='__main__':
    port=int(os.environ.get('PORT',3000))
    print(f'G&B GAME STORE v{get_setting("version","2.0.0")} on port {port}')
    socketio.run(app,host='0.0.0.0',port=port,debug=False)
