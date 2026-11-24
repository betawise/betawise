"""KJV mode benchmark origins and queries, independent of the C decoder."""
def cases():
 return [dict(query=q,mode=m,chapter=c,verse=v,word=0,direction=d)for c,v in [(596,80),(999,16)]for q in ['faith works','kingdom God','Jesus Jesus','be* bel*']for m in range(3)for d in [1,-1]]
