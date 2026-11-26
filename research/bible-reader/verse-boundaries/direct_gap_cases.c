int main(void) {
 unsigned checks=0;
 for(unsigned verse=1;verse<=176;++verse) for(unsigned mask=1;mask<=2;++mask) {
  uint8_t logical[64], raw[640]; unsigned n=0;
  logical[n++]=0xB1;logical[n++]=12;logical[n++]=0xB1;
  logical[n++]=0xB1;logical[n++]=mask;logical[n++]=0xB1;
  n+=sprintf((char*)logical+n,"%u",verse);
  logical[n++]=0xB2;logical[n++]=mask;logical[n++]=0xB2;
  logical[n++]=0xB2;logical[n++]=12;logical[n++]=0xB2;
  unsigned marker_length=n;
  memset(logical+n,'x',20);n+=20;g_chapter_file_bytes=n;
  for(unsigned split=0;split<=n;++split) for(unsigned gap=0;gap<=512;gap+=256) {
   memcpy(raw,logical,split);memset(raw+split,0xEE,gap);memcpy(raw+split+gap,logical+split,n-split);
   g_editor.gap_start=split;g_editor.gap_end=split+gap;
   for(unsigned pos=0;pos<=n;++pos) {
    BoundaryStream stream;stream.base=raw;stream.position=pos;stream.failed=false;
    BoundaryFill(&stream);
    assert(stream.available<=n-pos);
    assert(pos==n || stream.available);
    assert(!memcmp(stream.look,logical+pos,stream.available));
    unsigned length=0;unsigned number=BoundaryMarker(&stream,&length);
    assert(number==(pos==0?verse:0));
    if(number) assert(length==marker_length);
    ++checks;
   }
  }
 }
 printf("PASS %u direct-gap/marker assertions\n",checks);
 return 0;
}
