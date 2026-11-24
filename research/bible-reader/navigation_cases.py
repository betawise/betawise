"""Shared source-independent origins: (query, book number, chapter, verse, direction)."""
QUERIES=['God','believ','Methus']
ORIGINS=[(1,24,20),(19,119,80),(43,3,16)]
def cases(books):
 rows=[]
 for book,chapter,verse in ORIGINS:
  ci=sum(len(b['chapters'])for b in books[:book-1])+chapter-1
  for query in QUERIES:
   for direction in [1,-1]:rows.append(dict(query=query,chapter=ci,verse=verse,word=0,direction=direction))
 return rows
