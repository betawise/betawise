
Neo 3.21 original ROM (base 0x410000):     file format binary


Disassembly of section .data:

00428598 <.data+0x18598>:
  428598:	48e7 0018      	moveml %a3-%a4,%sp@-
  42859c:	266f 000c      	moveal %sp@(12),%a3
  4285a0:	286f 0010      	moveal %sp@(16),%a4
  4285a4:	4878 007c      	pea 0x7c
  4285a8:	42a7           	clrl %sp@-
  4285aa:	2f0c           	movel %a4,%sp@-
  4285ac:	4eb9 0043 66c2 	jsr 0x4366c2
  4285b2:	4fef 000c      	lea %sp@(12),%sp
  4285b6:	3893           	movew %a3@,%a4@
  4285b8:	422c 0002      	clrb %a4@(2)
  4285bc:	422c 0003      	clrb %a4@(3)
  4285c0:	426c 001c      	clrw %a4@(28)
  4285c4:	294b 0050      	movel %a3,%a4@(80)
  4285c8:	4cdf 1800      	moveml %sp@+,%a3-%a4
  4285cc:	4e75           	rts
  4285ce:	48e7 0338      	moveml %d6-%d7/%a2-%a4,%sp@-
  4285d2:	286f 0018      	moveal %sp@(24),%a4
  4285d6:	2e2f 001c      	movel %sp@(28),%d7
  4285da:	246f 0024      	moveal %sp@(36),%a2
  4285de:	266f 0020      	moveal %sp@(32),%a3
  4285e2:	4eb9 0043 5948 	jsr 0x435948
  4285e8:	6100 1aca      	bsrw 0x42a0b4
  4285ec:	4292           	clrl %a2@
  4285ee:	203c 0000 00ff 	movel #255,%d0
  4285f4:	c087           	andl %d7,%d0
  4285f6:	7220           	moveq #32,%d1
  4285f8:	b081           	cmpl %d1,%d0
  4285fa:	6200 0228      	bhiw 0x428824
  4285fe:	207c 0000 002f 	moveal #47,%a0
  428604:	720c           	moveq #12,%d1
  428606:	5288           	addql #1,%a0
  428608:	b03b 88fe      	cmpb %pc@(0x428608,%a0:l),%d0
  42860c:	53c9 fff8      	dbls %d1,0x428606
  428610:	6600 0212      	bnew 0x428824
  428614:	d281           	addl %d1,%d1
  428616:	323b 1806      	movew %pc@(0x42861e,%d1:l),%d1
  42861a:	4efb 1002      	jmp %pc@(0x42861e,%d1:w)
  42861e:	01d4           	bset %d0,%a4@
  428620:	01f8 0196      	bset %d0,0x196
  428624:	002c 017a 018e 	orib #122,%a4@(398)
  42862a:	0186           	bclr %d0,%d6
  42862c:	0088           	.short 0x0088
  42862e:	0162           	bchg %d0,%a2@-
  428630:	002c 010c 010c 	orib #12,%a4@(268)
  428636:	0028 0107 080b 	orib #7,%a0@(2059)
  42863c:	0c0d           	.short 0x0c0d
  42863e:	1011           	moveb %a1@,%d0
  428640:	1213           	moveb %a3@,%d1
  428642:	1e1f           	moveb %sp@+,%d7
  428644:	204e           	moveal %fp,%a0
  428646:	7011           	moveq #17,%d0
  428648:	2480           	movel %d0,%a2@
  42864a:	422c 0002      	clrb %a4@(2)
  42864e:	426c 001c      	clrw %a4@(28)
  428652:	0c87 0006 0001 	cmpil #393217,%d7
  428658:	6600 01c6      	bnew 0x428820
  42865c:	0c93 0000 0027 	cmpil #39,%a3@
  428662:	6304           	blss 0x428668
  428664:	7027           	moveq #39,%d0
  428666:	2680           	movel %d0,%a3@
  428668:	2f13           	movel %a3@,%sp@-
  42866a:	2f2b 0004      	movel %a3@(4),%sp@-
  42866e:	486c 0020      	pea %a4@(32)
  428672:	4eb9 0043 6b46 	jsr 0x436b46
  428678:	4fef 000c      	lea %sp@(12),%sp
  42867c:	2013           	movel %a3@,%d0
  42867e:	4234 0820      	clrb %a4@(20,%d0:l)
  428682:	6014           	bras 0x428698
  428684:	5393           	subql #1,%a3@
  428686:	2013           	movel %a3@,%d0
  428688:	0c34 0020 0820 	cmpib #32,%a4@(20,%d0:l)
  42868e:	6406           	bccs 0x428696
  428690:	4234 0820      	clrb %a4@(20,%d0:l)
  428694:	6002           	bras 0x428698
  428696:	4293           	clrl %a3@
  428698:	4a93           	tstl %a3@
  42869a:	66e8           	bnes 0x428684
  42869c:	197c 0006 0002 	moveb #6,%a4@(2)
  4286a2:	6000 017c      	braw 0x428820
  4286a6:	0c2c 0006 0002 	cmpib #6,%a4@(2)
  4286ac:	667c           	bnes 0x42872a
  4286ae:	42a7           	clrl %sp@-
  4286b0:	486c 0050      	pea %a4@(80)
  4286b4:	2f2c 0050      	movel %a4@(80),%sp@-
  4286b8:	6100 0a48      	bsrw 0x429102
  4286bc:	42a7           	clrl %sp@-
  4286be:	42a7           	clrl %sp@-
  4286c0:	42a7           	clrl %sp@-
  4286c2:	42a7           	clrl %sp@-
  4286c4:	42a7           	clrl %sp@-
  4286c6:	42a7           	clrl %sp@-
  4286c8:	42a7           	clrl %sp@-
  4286ca:	486c 004c      	pea %a4@(76)
  4286ce:	7000           	moveq #0,%d0
  4286d0:	3014           	movew %a4@,%d0
  4286d2:	2f00           	movel %d0,%sp@-
  4286d4:	4eb9 0043 a53e 	jsr 0x43a53e
  4286da:	588f           	addql #4,%sp
  4286dc:	2f00           	movel %d0,%sp@-
  4286de:	42a7           	clrl %sp@-
  4286e0:	7000           	moveq #0,%d0
  4286e2:	3014           	movew %a4@,%d0
  4286e4:	2f00           	movel %d0,%sp@-
  4286e6:	6100 1256      	bsrw 0x42993e
  4286ea:	4fef 0038      	lea %sp@(56),%sp
  4286ee:	42ac 0048      	clrl %a4@(72)
  4286f2:	197c 0007 0002 	moveb #7,%a4@(2)
  4286f8:	422c 0003      	clrb %a4@(3)
  4286fc:	426c 001c      	clrw %a4@(28)
  428700:	202c 004c      	movel %a4@(76),%d0
  428704:	7219           	moveq #25,%d1
  428706:	4eb9 0043 73fc 	jsr 0x4373fc
  42870c:	3940 001e      	movew %d0,%a4@(30)
  428710:	0c40 0028      	cmpiw #40,%d0
  428714:	6306           	blss 0x42871c
  428716:	397c 0028 001e 	movew #40,%a4@(30)
  42871c:	0c6c 000a 001e 	cmpiw #10,%a4@(30)
  428722:	6406           	bccs 0x42872a
  428724:	397c 000a 001e 	movew #10,%a4@(30)
  42872a:	0c2c 0002 0002 	cmpib #2,%a4@(2)
  428730:	6718           	beqs 0x42874a
  428732:	0c2c 0005 0002 	cmpib #5,%a4@(2)
  428738:	6710           	beqs 0x42874a
  42873a:	0c2c 0008 0002 	cmpib #8,%a4@(2)
  428740:	6708           	beqs 0x42874a
  428742:	0c2c 0009 0002 	cmpib #9,%a4@(2)
  428748:	6622           	bnes 0x42876c
  42874a:	0c2c 0008 0002 	cmpib #8,%a4@(2)
  428750:	6708           	beqs 0x42875a
  428752:	0c2c 0009 0002 	cmpib #9,%a4@(2)
  428758:	660c           	bnes 0x428766
  42875a:	197c 0006 0002 	moveb #6,%a4@(2)
  428760:	7008           	moveq #8,%d0
  428762:	2480           	movel %d0,%a2@
  428764:	6038           	bras 0x42879e
  428766:	422c 0002      	clrb %a4@(2)
  42876a:	6032           	bras 0x42879e
  42876c:	0c2c 0001 0002 	cmpib #1,%a4@(2)
  428772:	6754           	beqs 0x4287c8
  428774:	0c2c 0007 0002 	cmpib #7,%a4@(2)
  42877a:	6600 00a4      	bnew 0x428820
  42877e:	6048           	bras 0x4287c8
  428780:	0c87 0006 000c 	cmpil #393228,%d7
  428786:	6608           	bnes 0x428790
  428788:	197c 000a 0002 	moveb #10,%a4@(2)
  42878e:	600e           	bras 0x42879e
  428790:	197c 0004 0002 	moveb #4,%a4@(2)
  428796:	6006           	bras 0x42879e
  428798:	197c 0003 0002 	moveb #3,%a4@(2)
  42879e:	426c 001c      	clrw %a4@(28)
  4287a2:	607c           	bras 0x428820
  4287a4:	197c 000b 0002 	moveb #11,%a4@(2)
  4287aa:	6074           	bras 0x428820
  4287ac:	197c 0007 0002 	moveb #7,%a4@(2)
  4287b2:	606c           	bras 0x428820
  4287b4:	206b 0004      	moveal %a3@(4),%a0
  4287b8:	3e10           	movew %a0@,%d7
  4287ba:	4a2c 0002      	tstb %a4@(2)
  4287be:	6618           	bnes 0x4287d8
  4287c0:	3007           	movew %d7,%d0
  4287c2:	0c00 002a      	cmpib #42,%d0
  4287c6:	6610           	bnes 0x4287d8
  4287c8:	2f0a           	movel %a2,%sp@-
  4287ca:	2f0b           	movel %a3,%sp@-
  4287cc:	2f0c           	movel %a4,%sp@-
  4287ce:	6100 1744      	bsrw 0x429f14
  4287d2:	4fef 000c      	lea %sp@(12),%sp
  4287d6:	6048           	bras 0x428820
  4287d8:	0c2c 0001 0002 	cmpib #1,%a4@(2)
  4287de:	6644           	bnes 0x428824
  4287e0:	0c47 0048      	cmpiw #72,%d7
  4287e4:	6636           	bnes 0x42881c
  4287e6:	7013           	moveq #19,%d0
  4287e8:	2480           	movel %d0,%a2@
  4287ea:	197c 0002 0002 	moveb #2,%a4@(2)
  4287f0:	602e           	bras 0x428820
  4287f2:	206b 0004      	moveal %a3@(4),%a0
  4287f6:	3c10           	movew %a0@,%d6
  4287f8:	0c87 0006 0020 	cmpil #393248,%d7
  4287fe:	6624           	bnes 0x428824
  428800:	7001           	moveq #1,%d0
  428802:	2480           	movel %d0,%a2@
  428804:	0c46 0048      	cmpiw #72,%d6
  428808:	6616           	bnes 0x428820
  42880a:	197c 0008 0002 	moveb #8,%a4@(2)
  428810:	7008           	moveq #8,%d0
  428812:	2480           	movel %d0,%a2@
  428814:	600a           	bras 0x428820
  428816:	4a2c 0002      	tstb %a4@(2)
  42881a:	6708           	beqs 0x428824
  42881c:	7001           	moveq #1,%d0
  42881e:	2480           	movel %d0,%a2@
  428820:	7001           	moveq #1,%d0
  428822:	6002           	bras 0x428826
  428824:	7000           	moveq #0,%d0
  428826:	4cdf 1cc0      	moveml %sp@+,%d6-%d7/%a2-%a4
  42882a:	4e75           	rts
