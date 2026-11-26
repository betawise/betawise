
Neo 3.21 memory dump (base 0x420000):     file format binary


Disassembly of section .data:

0042a0f8 <.data+0xa0f8>:
  42a0f8:	48e7 3f3a      	moveml %d2-%d7/%a2-%a4/%fp,%sp@-
  42a0fc:	4fef ffe6      	lea %sp@(-26),%sp
  42a100:	266f 0046      	moveal %sp@(70),%a3
  42a104:	42a7           	clrl %sp@-
  42a106:	42a7           	clrl %sp@-
  42a108:	42a7           	clrl %sp@-
  42a10a:	42a7           	clrl %sp@-
  42a10c:	7000           	moveq #0,%d0
  42a10e:	3013           	movew %a3@,%d0
  42a110:	2f00           	movel %d0,%sp@-
  42a112:	4eb9 0043 a81c 	jsr 0x43a81c
  42a118:	2c40           	moveal %d0,%fp
  42a11a:	202b 0018      	movel %a3@(24),%d0
  42a11e:	d08e           	addl %fp,%d0
  42a120:	2840           	moveal %d0,%a4
  42a122:	7000           	moveq #0,%d0
  42a124:	3013           	movew %a3@,%d0
  42a126:	2f00           	movel %d0,%sp@-
  42a128:	4eb9 0043 a53e 	jsr 0x43a53e
  42a12e:	4fef 0018      	lea %sp@(24),%sp
  42a132:	d08e           	addl %fp,%d0
  42a134:	2440           	moveal %d0,%a2
  42a136:	342b 0022      	movew %a3@(34),%d2
  42a13a:	4245           	clrw %d5
  42a13c:	3e02           	movew %d2,%d7
  42a13e:	42af 0012      	clrl %sp@(18)
  42a142:	2f6b 004e 000e 	movel %a3@(78),%sp@(14)
  42a148:	162b 0021      	moveb %a3@(33),%d3
  42a14c:	42af 000a      	clrl %sp@(10)
  42a150:	42af 0006      	clrl %sp@(6)
  42a154:	4297           	clrl %sp@
  42a156:	082b 0002 000d 	btst #2,%a3@(13)
  42a15c:	6608           	bnes 0x42a166
  42a15e:	082b 0003 000d 	btst #3,%a3@(13)
  42a164:	670e           	beqs 0x42a174
  42a166:	303c fffa      	movew #-6,%d0
  42a16a:	d06b 0012      	addw %a3@(18),%d0
  42a16e:	3f40 0004      	movew %d0,%sp@(4)
  42a172:	6006           	bras 0x42a17a
  42a174:	3f6b 0012 0004 	movew %a3@(18),%sp@(4)
  42a17a:	4878 000c      	pea 0xc
  42a17e:	302b 003e      	movew %a3@(62),%d0
  42a182:	d06b 0010      	addw %a3@(16),%d0
  42a186:	7200           	moveq #0,%d1
  42a188:	3200           	movew %d0,%d1
  42a18a:	2001           	movel %d1,%d0
  42a18c:	2f00           	movel %d0,%sp@-
  42a18e:	302b 003c      	movew %a3@(60),%d0
  42a192:	d06b 000e      	addw %a3@(14),%d0
  42a196:	7200           	moveq #0,%d1
  42a198:	3200           	movew %d0,%d1
  42a19a:	2001           	movel %d1,%d0
  42a19c:	2f00           	movel %d0,%sp@-
  42a19e:	4eb9 0042 21f4 	jsr 0x4221f4
  42a1a4:	7000           	moveq #0,%d0
  42a1a6:	1003           	moveb %d3,%d0
  42a1a8:	2f00           	movel %d0,%sp@-
  42a1aa:	486f 001e      	pea %sp@(30)
  42a1ae:	2f0b           	movel %a3,%sp@-
  42a1b0:	4eb9 0042 e62e 	jsr 0x42e62e
  42a1b6:	4fef 0018      	lea %sp@(24),%sp
  42a1ba:	0c6b 0001 0036 	cmpiw #1,%a3@(54)
  42a1c0:	662c           	bnes 0x42a1ee
  42a1c2:	202b 0038      	movel %a3@(56),%d0
  42a1c6:	b0ab 0024      	cmpl %a3@(36),%d0
  42a1ca:	6412           	bccs 0x42a1de
  42a1cc:	d08e           	addl %fp,%d0
  42a1ce:	2f40 000a      	movel %d0,%sp@(10)
  42a1d2:	202b 0024      	movel %a3@(36),%d0
  42a1d6:	d08e           	addl %fp,%d0
  42a1d8:	2f40 0006      	movel %d0,%sp@(6)
  42a1dc:	6010           	bras 0x42a1ee
  42a1de:	d08e           	addl %fp,%d0
  42a1e0:	2f40 0006      	movel %d0,%sp@(6)
  42a1e4:	202b 0024      	movel %a3@(36),%d0
  42a1e8:	d08e           	addl %fp,%d0
  42a1ea:	2f40 000a      	movel %d0,%sp@(10)
  42a1ee:	0c6b 0003 0036 	cmpiw #3,%a3@(54)
  42a1f4:	6600 05cc      	bnew 0x42a7c2
  42a1f8:	4a39 0000 7e06 	tstb 0x7e06
  42a1fe:	6700 008e      	beqw 0x42a28e
  42a202:	2039 0000 7e08 	movel 0x7e08,%d0
  42a208:	b0ab 0038      	cmpl %a3@(56),%d0
  42a20c:	6518           	bcss 0x42a226
  42a20e:	4879 0000 7e08 	pea 0x7e08
  42a214:	2f2b 0038      	movel %a3@(56),%sp@-
  42a218:	2f0b           	movel %a3,%sp@-
  42a21a:	4eb9 0042 cd5a 	jsr 0x42cd5a
  42a220:	4fef 000c      	lea %sp@(12),%sp
  42a224:	6058           	bras 0x42a27e
  42a226:	4878 0020      	pea 0x20
  42a22a:	486f 0016      	pea %sp@(22)
  42a22e:	2f2b 004e      	movel %a3@(78),%sp@-
  42a232:	4eb9 0042 bece 	jsr 0x42bece
  42a238:	42a7           	clrl %sp@-
  42a23a:	42a7           	clrl %sp@-
  42a23c:	42a7           	clrl %sp@-
  42a23e:	486f 0018      	pea %sp@(24)
  42a242:	42a7           	clrl %sp@-
  42a244:	42a7           	clrl %sp@-
  42a246:	42a7           	clrl %sp@-
  42a248:	42a7           	clrl %sp@-
  42a24a:	2f2b 0038      	movel %a3@(56),%sp@-
  42a24e:	2f39 0000 7e08 	movel 0x7e08,%sp@-
  42a254:	7000           	moveq #0,%d0
  42a256:	3013           	movew %a3@,%d0
  42a258:	2f00           	movel %d0,%sp@-
  42a25a:	4eb9 0042 993e 	jsr 0x42993e
  42a260:	4fef 0038      	lea %sp@(56),%sp
  42a264:	7042           	moveq #66,%d0
  42a266:	222f 0012      	movel %sp@(18),%d1
  42a26a:	4eb9 0043 73fc 	jsr 0x4373fc
  42a270:	2217           	movel %sp@,%d1
  42a272:	b280           	cmpl %d0,%d1
  42a274:	6508           	bcss 0x42a27e
  42a276:	23eb 0038 0000 	movel %a3@(56),0x7e08
  42a27c:	7e08 
  42a27e:	2039 0000 7e08 	movel 0x7e08,%d0
  42a284:	b0ab 0018      	cmpl %a3@(24),%d0
  42a288:	6404           	bccs 0x42a28e
  42a28a:	d08e           	addl %fp,%d0
  42a28c:	2840           	moveal %d0,%a4
  42a28e:	202b 0038      	movel %a3@(56),%d0
  42a292:	b0b9 0000 7e0e 	cmpl 0x7e0e,%d0
  42a298:	6416           	bccs 0x42a2b0
  42a29a:	d08e           	addl %fp,%d0
  42a29c:	2f40 000a      	movel %d0,%sp@(10)
  42a2a0:	2039 0000 7e0e 	movel 0x7e0e,%d0
  42a2a6:	d08e           	addl %fp,%d0
  42a2a8:	2f40 0006      	movel %d0,%sp@(6)
  42a2ac:	6000 0514      	braw 0x42a7c2
  42a2b0:	d08e           	addl %fp,%d0
  42a2b2:	2f40 0006      	movel %d0,%sp@(6)
  42a2b6:	2039 0000 7e0e 	movel 0x7e0e,%d0
  42a2bc:	d08e           	addl %fp,%d0
  42a2be:	2f40 000a      	movel %d0,%sp@(10)
  42a2c2:	6000 04fe      	braw 0x42a7c2
  42a2c6:	b9ef 000a      	cmpal %sp@(10),%a4
  42a2ca:	650a           	bcss 0x42a2d6
  42a2cc:	b9ef 0006      	cmpal %sp@(6),%a4
  42a2d0:	6404           	bccs 0x42a2d6
  42a2d2:	7801           	moveq #1,%d4
  42a2d4:	6002           	bras 0x42a2d8
  42a2d6:	4204           	clrb %d4
  42a2d8:	1c14           	moveb %a4@,%d6
  42a2da:	7200           	moveq #0,%d1
  42a2dc:	1206           	moveb %d6,%d1
  42a2de:	0681 0044 c7e0 	addil #4507616,%d1
  42a2e4:	2041           	moveal %d1,%a0
  42a2e6:	1010           	moveb %a0@,%d0
  42a2e8:	0c00 0014      	cmpib #20,%d0
  42a2ec:	6200 04d4      	bhiw 0x42a7c2
  42a2f0:	4880           	extw %d0
  42a2f2:	d040           	addw %d0,%d0
  42a2f4:	303b 0006      	movew %pc@(0x42a2fc,%d0:w),%d0
  42a2f8:	4efb 0002      	jmp %pc@(0x42a2fc,%d0:w)
  42a2fc:	00e2           	.short 0x00e2
  42a2fe:	0268 00e2 018e 	andiw #226,%a0@(398)
  42a304:	002a 01f8 00e2 	orib #-8,%a2@(226)
  42a30a:	0136 018e 0268 	btst %d0,@(0)@(268,%d0:w)
  42a310:	0316           	btst %d1,%fp@
  42a312:	0360           	bchg %d1,%a0@-
  42a314:	033c 0348      	btst %d1,#72
  42a318:	0362           	bchg %d1,%a2@-
  42a31a:	0368 03be      	bchg %d1,%a0@(958)
  42a31e:	046c 04ba 04be 	subiw #1210,%a4@(1214)
  42a324:	04be           	.short 0x04be
  42a326:	7000           	moveq #0,%d0
  42a328:	3007           	movew %d7,%d0
  42a32a:	2f00           	movel %d0,%sp@-
  42a32c:	204f           	moveal %sp,%a0
  42a32e:	2f28 0012      	movel %a0@(18),%sp@-
  42a332:	4eb9 0042 bf0a 	jsr 0x42bf0a
  42a338:	508f           	addql #8,%sp
  42a33a:	d047           	addw %d7,%d0
  42a33c:	3f40 0018      	movew %d0,%sp@(24)
  42a340:	4a6b 004c      	tstw %a3@(76)
  42a344:	6750           	beqs 0x42a396
  42a346:	7000           	moveq #0,%d0
  42a348:	1004           	moveb %d4,%d0
  42a34a:	2f00           	movel %d0,%sp@-
  42a34c:	7000           	moveq #0,%d0
  42a34e:	1006           	moveb %d6,%d0
  42a350:	2f00           	movel %d0,%sp@-
  42a352:	302b 0010      	movew %a3@(16),%d0
  42a356:	d045           	addw %d5,%d0
  42a358:	7200           	moveq #0,%d1
  42a35a:	3200           	movew %d0,%d1
  42a35c:	2001           	movel %d1,%d0
  42a35e:	2f00           	movel %d0,%sp@-
  42a360:	302b 000e      	movew %a3@(14),%d0
  42a364:	d047           	addw %d7,%d0
  42a366:	7200           	moveq #0,%d1
  42a368:	3200           	movew %d0,%d1
  42a36a:	2001           	movel %d1,%d0
  42a36c:	2f00           	movel %d0,%sp@-
  42a36e:	204f           	moveal %sp,%a0
  42a370:	2f28 001e      	movel %a0@(30),%sp@-
  42a374:	4eb9 0042 1a82 	jsr 0x421a82
  42a37a:	7000           	moveq #0,%d0
  42a37c:	1014           	moveb %a4@,%d0
  42a37e:	2f00           	movel %d0,%sp@-
  42a380:	486f 002a      	pea %sp@(42)
  42a384:	204f           	moveal %sp,%a0
  42a386:	2f28 002a      	movel %a0@(42),%sp@-
  42a38a:	4eb9 0042 bece 	jsr 0x42bece
  42a390:	4fef 0020      	lea %sp@(32),%sp
  42a394:	de40           	addw %d0,%d7
  42a396:	7000           	moveq #0,%d0
  42a398:	1004           	moveb %d4,%d0
  42a39a:	2f00           	movel %d0,%sp@-
  42a39c:	302f 001c      	movew %sp@(28),%d0
  42a3a0:	9047           	subw %d7,%d0
  42a3a2:	7200           	moveq #0,%d1
  42a3a4:	3200           	movew %d0,%d1
  42a3a6:	2001           	movel %d1,%d0
  42a3a8:	2f00           	movel %d0,%sp@-
  42a3aa:	302b 0010      	movew %a3@(16),%d0
  42a3ae:	d045           	addw %d5,%d0
  42a3b0:	7200           	moveq #0,%d1
  42a3b2:	3200           	movew %d0,%d1
  42a3b4:	2001           	movel %d1,%d0
  42a3b6:	2f00           	movel %d0,%sp@-
  42a3b8:	302b 000e      	movew %a3@(14),%d0
  42a3bc:	d047           	addw %d7,%d0
  42a3be:	7200           	moveq #0,%d1
  42a3c0:	3200           	movew %d0,%d1
  42a3c2:	2001           	movel %d1,%d0
  42a3c4:	2f00           	movel %d0,%sp@-
  42a3c6:	204f           	moveal %sp,%a0
  42a3c8:	2f28 001e      	movel %a0@(30),%sp@-
  42a3cc:	4eb9 0042 1cf4 	jsr 0x421cf4
  42a3d2:	4fef 0014      	lea %sp@(20),%sp
  42a3d6:	3e2f 0018      	movew %sp@(24),%d7
  42a3da:	6000 0282      	braw 0x42a65e
  42a3de:	7000           	moveq #0,%d0
  42a3e0:	1004           	moveb %d4,%d0
  42a3e2:	2f00           	movel %d0,%sp@-
  42a3e4:	7000           	moveq #0,%d0
  42a3e6:	1006           	moveb %d6,%d0
  42a3e8:	2f00           	movel %d0,%sp@-
  42a3ea:	302b 0010      	movew %a3@(16),%d0
  42a3ee:	d045           	addw %d5,%d0
  42a3f0:	7200           	moveq #0,%d1
  42a3f2:	3200           	movew %d0,%d1
  42a3f4:	2001           	movel %d1,%d0
  42a3f6:	2f00           	movel %d0,%sp@-
  42a3f8:	302b 000e      	movew %a3@(14),%d0
  42a3fc:	d047           	addw %d7,%d0
  42a3fe:	7200           	moveq #0,%d1
  42a400:	3200           	movew %d0,%d1
  42a402:	2001           	movel %d1,%d0
  42a404:	2f00           	movel %d0,%sp@-
  42a406:	204f           	moveal %sp,%a0
  42a408:	2f28 001e      	movel %a0@(30),%sp@-
  42a40c:	4eb9 0042 1a82 	jsr 0x421a82
  42a412:	7000           	moveq #0,%d0
  42a414:	1014           	moveb %a4@,%d0
  42a416:	2f00           	movel %d0,%sp@-
  42a418:	486f 002a      	pea %sp@(42)
  42a41c:	204f           	moveal %sp,%a0
  42a41e:	2f28 002a      	movel %a0@(42),%sp@-
  42a422:	4eb9 0042 bece 	jsr 0x42bece
  42a428:	4fef 0020      	lea %sp@(32),%sp
  42a42c:	de40           	addw %d0,%d7
  42a42e:	6000 022e      	braw 0x42a65e
  42a432:	1014           	moveb %a4@,%d0
  42a434:	b006           	cmpb %d6,%d0
  42a436:	6602           	bnes 0x42a43a
  42a438:	7c2d           	moveq #45,%d6
  42a43a:	7000           	moveq #0,%d0
  42a43c:	1004           	moveb %d4,%d0
  42a43e:	2f00           	movel %d0,%sp@-
  42a440:	7000           	moveq #0,%d0
  42a442:	1006           	moveb %d6,%d0
  42a444:	2f00           	movel %d0,%sp@-
  42a446:	302b 0010      	movew %a3@(16),%d0
  42a44a:	d045           	addw %d5,%d0
  42a44c:	7200           	moveq #0,%d1
  42a44e:	3200           	movew %d0,%d1
  42a450:	2001           	movel %d1,%d0
  42a452:	2f00           	movel %d0,%sp@-
  42a454:	302b 000e      	movew %a3@(14),%d0
  42a458:	d047           	addw %d7,%d0
  42a45a:	7200           	moveq #0,%d1
  42a45c:	3200           	movew %d0,%d1
  42a45e:	2001           	movel %d1,%d0
  42a460:	2f00           	movel %d0,%sp@-
  42a462:	204f           	moveal %sp,%a0
  42a464:	2f28 001e      	movel %a0@(30),%sp@-
  42a468:	4eb9 0042 1a82 	jsr 0x421a82
  42a46e:	7000           	moveq #0,%d0
  42a470:	1006           	moveb %d6,%d0
  42a472:	2f00           	movel %d0,%sp@-
  42a474:	486f 002a      	pea %sp@(42)
  42a478:	204f           	moveal %sp,%a0
  42a47a:	2f28 002a      	movel %a0@(42),%sp@-
  42a47e:	4eb9 0042 bece 	jsr 0x42bece
  42a484:	4fef 0020      	lea %sp@(32),%sp
  42a488:	de40           	addw %d0,%d7
  42a48a:	7000           	moveq #0,%d0
  42a48c:	1014           	moveb %a4@,%d0
  42a48e:	0680 0044 c7e0 	addil #4507616,%d0
  42a494:	2040           	moveal %d0,%a0
  42a496:	0c10 0007      	cmpib #7,%a0@
  42a49a:	6758           	beqs 0x42a4f4
  42a49c:	4242           	clrw %d2
  42a49e:	4a6b 004c      	tstw %a3@(76)
  42a4a2:	6750           	beqs 0x42a4f4
  42a4a4:	7000           	moveq #0,%d0
  42a4a6:	1004           	moveb %d4,%d0
  42a4a8:	2f00           	movel %d0,%sp@-
  42a4aa:	7000           	moveq #0,%d0
  42a4ac:	1006           	moveb %d6,%d0
  42a4ae:	2f00           	movel %d0,%sp@-
  42a4b0:	302b 0010      	movew %a3@(16),%d0
  42a4b4:	d045           	addw %d5,%d0
  42a4b6:	7200           	moveq #0,%d1
  42a4b8:	3200           	movew %d0,%d1
  42a4ba:	2001           	movel %d1,%d0
  42a4bc:	2f00           	movel %d0,%sp@-
  42a4be:	302b 000e      	movew %a3@(14),%d0
  42a4c2:	d047           	addw %d7,%d0
  42a4c4:	7200           	moveq #0,%d1
  42a4c6:	3200           	movew %d0,%d1
  42a4c8:	2001           	movel %d1,%d0
  42a4ca:	2f00           	movel %d0,%sp@-
  42a4cc:	204f           	moveal %sp,%a0
  42a4ce:	2f28 001e      	movel %a0@(30),%sp@-
  42a4d2:	4eb9 0042 1a82 	jsr 0x421a82
  42a4d8:	7000           	moveq #0,%d0
  42a4da:	1006           	moveb %d6,%d0
  42a4dc:	2f00           	movel %d0,%sp@-
  42a4de:	486f 002a      	pea %sp@(42)
  42a4e2:	204f           	moveal %sp,%a0
  42a4e4:	2f28 002a      	movel %a0@(42),%sp@-
  42a4e8:	4eb9 0042 bece 	jsr 0x42bece
  42a4ee:	4fef 0020      	lea %sp@(32),%sp
  42a4f2:	de40           	addw %d0,%d7
  42a4f4:	7000           	moveq #0,%d0
  42a4f6:	1014           	moveb %a4@,%d0
  42a4f8:	0680 0044 c7e0 	addil #4507616,%d0
  42a4fe:	2040           	moveal %d0,%a0
  42a500:	0c10 0005      	cmpib #5,%a0@
  42a504:	665e           	bnes 0x42a564
  42a506:	4a6b 004c      	tstw %a3@(76)
  42a50a:	6758           	beqs 0x42a564
  42a50c:	0c06 008d      	cmpib #-115,%d6
  42a510:	6602           	bnes 0x42a514
  42a512:	7c09           	moveq #9,%d6
  42a514:	7000           	moveq #0,%d0
  42a516:	1004           	moveb %d4,%d0
  42a518:	2f00           	movel %d0,%sp@-
  42a51a:	7000           	moveq #0,%d0
  42a51c:	1006           	moveb %d6,%d0
  42a51e:	2f00           	movel %d0,%sp@-
  42a520:	302b 0010      	movew %a3@(16),%d0
  42a524:	d045           	addw %d5,%d0
  42a526:	7200           	moveq #0,%d1
  42a528:	3200           	movew %d0,%d1
  42a52a:	2001           	movel %d1,%d0
  42a52c:	2f00           	movel %d0,%sp@-
  42a52e:	302b 000e      	movew %a3@(14),%d0
  42a532:	d047           	addw %d7,%d0
  42a534:	7200           	moveq #0,%d1
  42a536:	3200           	movew %d0,%d1
  42a538:	2001           	movel %d1,%d0
  42a53a:	2f00           	movel %d0,%sp@-
  42a53c:	204f           	moveal %sp,%a0
  42a53e:	2f28 001e      	movel %a0@(30),%sp@-
  42a542:	4eb9 0042 1a82 	jsr 0x421a82
  42a548:	7000           	moveq #0,%d0
  42a54a:	1006           	moveb %d6,%d0
  42a54c:	2f00           	movel %d0,%sp@-
  42a54e:	486f 002a      	pea %sp@(42)
  42a552:	204f           	moveal %sp,%a0
  42a554:	2f28 002a      	movel %a0@(42),%sp@-
  42a558:	4eb9 0042 bece 	jsr 0x42bece
  42a55e:	4fef 0020      	lea %sp@(32),%sp
  42a562:	de40           	addw %d0,%d7
  42a564:	528c           	addql #1,%a4
  42a566:	7000           	moveq #0,%d0
  42a568:	1004           	moveb %d4,%d0
  42a56a:	2f00           	movel %d0,%sp@-
  42a56c:	302f 0008      	movew %sp@(8),%d0
  42a570:	9047           	subw %d7,%d0
  42a572:	7200           	moveq #0,%d1
  42a574:	3200           	movew %d0,%d1
  42a576:	2001           	movel %d1,%d0
  42a578:	2f00           	movel %d0,%sp@-
  42a57a:	302b 0010      	movew %a3@(16),%d0
  42a57e:	d045           	addw %d5,%d0
  42a580:	7200           	moveq #0,%d1
  42a582:	3200           	movew %d0,%d1
  42a584:	2001           	movel %d1,%d0
  42a586:	2f00           	movel %d0,%sp@-
  42a588:	302b 000e      	movew %a3@(14),%d0
  42a58c:	d047           	addw %d7,%d0
  42a58e:	7200           	moveq #0,%d1
  42a590:	3200           	movew %d0,%d1
  42a592:	2001           	movel %d1,%d0
  42a594:	2f00           	movel %d0,%sp@-
  42a596:	204f           	moveal %sp,%a0
  42a598:	2f28 001e      	movel %a0@(30),%sp@-
  42a59c:	4eb9 0042 1cf4 	jsr 0x421cf4
  42a5a2:	4fef 0014      	lea %sp@(20),%sp
  42a5a6:	4247           	clrw %d7
  42a5a8:	4aaf 0012      	tstl %sp@(18)
  42a5ac:	6618           	bnes 0x42a5c6
  42a5ae:	4878 0020      	pea 0x20
  42a5b2:	486f 0016      	pea %sp@(22)
  42a5b6:	204f           	moveal %sp,%a0
  42a5b8:	2f28 0016      	movel %a0@(22),%sp@-
  42a5bc:	4eb9 0042 bece 	jsr 0x42bece
  42a5c2:	4fef 000c      	lea %sp@(12),%sp
  42a5c6:	da6f 0014      	addw %sp@(20),%d5
  42a5ca:	4a42           	tstw %d2
  42a5cc:	6700 01f4      	beqw 0x42a7c2
  42a5d0:	7000           	moveq #0,%d0
  42a5d2:	1004           	moveb %d4,%d0
  42a5d4:	2f00           	movel %d0,%sp@-
  42a5d6:	3002           	movew %d2,%d0
  42a5d8:	9047           	subw %d7,%d0
  42a5da:	7200           	moveq #0,%d1
  42a5dc:	3200           	movew %d0,%d1
  42a5de:	2f01           	movel %d1,%sp@-
  42a5e0:	302b 0010      	movew %a3@(16),%d0
  42a5e4:	d045           	addw %d5,%d0
  42a5e6:	7200           	moveq #0,%d1
  42a5e8:	3200           	movew %d0,%d1
  42a5ea:	2001           	movel %d1,%d0
  42a5ec:	2f00           	movel %d0,%sp@-
  42a5ee:	302b 000e      	movew %a3@(14),%d0
  42a5f2:	d047           	addw %d7,%d0
  42a5f4:	7200           	moveq #0,%d1
  42a5f6:	3200           	movew %d0,%d1
  42a5f8:	2001           	movel %d1,%d0
  42a5fa:	2f00           	movel %d0,%sp@-
  42a5fc:	204f           	moveal %sp,%a0
  42a5fe:	2f28 001e      	movel %a0@(30),%sp@-
  42a602:	4eb9 0042 1cf4 	jsr 0x421cf4
  42a608:	4fef 0014      	lea %sp@(20),%sp
  42a60c:	3e02           	movew %d2,%d7
  42a60e:	6000 01b2      	braw 0x42a7c2
  42a612:	202b 002c      	movel %a3@(44),%d0
  42a616:	d08e           	addl %fp,%d0
  42a618:	2f40 0016      	movel %d0,%sp@(22)
  42a61c:	b08c           	cmpl %a4,%d0
  42a61e:	630a           	blss 0x42a62a
  42a620:	b08a           	cmpl %a2,%d0
  42a622:	6206           	bhis 0x42a62a
  42a624:	2840           	moveal %d0,%a4
  42a626:	6000 019a      	braw 0x42a7c2
  42a62a:	202f 0016      	movel %sp@(22),%d0
  42a62e:	b08a           	cmpl %a2,%d0
  42a630:	632c           	blss 0x42a65e
  42a632:	284a           	moveal %a2,%a4
  42a634:	6000 018c      	braw 0x42a7c2
  42a638:	be42           	cmpw %d2,%d7
  42a63a:	6600 0186      	bnew 0x42a7c2
  42a63e:	4247           	clrw %d7
  42a640:	6000 0180      	braw 0x42a7c2
  42a644:	528c           	addql #1,%a4
  42a646:	6002           	bras 0x42a64a
  42a648:	528c           	addql #1,%a4
  42a64a:	b9ca           	cmpal %a2,%a4
  42a64c:	6406           	bccs 0x42a654
  42a64e:	0c14 009d      	cmpib #-99,%a4@
  42a652:	66f4           	bnes 0x42a648
  42a654:	b9ca           	cmpal %a2,%a4
  42a656:	6700 016a      	beqw 0x42a7c2
  42a65a:	6002           	bras 0x42a65e
  42a65c:	3407           	movew %d7,%d2
  42a65e:	528c           	addql #1,%a4
  42a660:	6000 0160      	braw 0x42a7c2
  42a664:	528c           	addql #1,%a4
  42a666:	7000           	moveq #0,%d0
  42a668:	1004           	moveb %d4,%d0
  42a66a:	2f00           	movel %d0,%sp@-
  42a66c:	7000           	moveq #0,%d0
  42a66e:	1014           	moveb %a4@,%d0
  42a670:	2f00           	movel %d0,%sp@-
  42a672:	302b 0010      	movew %a3@(16),%d0
  42a676:	d045           	addw %d5,%d0
  42a678:	7200           	moveq #0,%d1
  42a67a:	3200           	movew %d0,%d1
  42a67c:	2001           	movel %d1,%d0
  42a67e:	2f00           	movel %d0,%sp@-
  42a680:	302b 000e      	movew %a3@(14),%d0
  42a684:	d047           	addw %d7,%d0
  42a686:	7200           	moveq #0,%d1
  42a688:	3200           	movew %d0,%d1
  42a68a:	2001           	movel %d1,%d0
  42a68c:	2f00           	movel %d0,%sp@-
  42a68e:	204f           	moveal %sp,%a0
  42a690:	2f28 001e      	movel %a0@(30),%sp@-
  42a694:	4eb9 0042 1a82 	jsr 0x421a82
  42a69a:	7000           	moveq #0,%d0
  42a69c:	1014           	moveb %a4@,%d0
  42a69e:	2f00           	movel %d0,%sp@-
  42a6a0:	486f 002a      	pea %sp@(42)
  42a6a4:	204f           	moveal %sp,%a0
  42a6a6:	2f28 002a      	movel %a0@(42),%sp@-
  42a6aa:	4eb9 0042 bece 	jsr 0x42bece
  42a6b0:	4fef 0020      	lea %sp@(32),%sp
  42a6b4:	de40           	addw %d0,%d7
  42a6b6:	6000 00fa      	braw 0x42a7b2
  42a6ba:	528c           	addql #1,%a4
  42a6bc:	8614           	orb %a4@,%d3
  42a6be:	548c           	addql #2,%a4
  42a6c0:	7000           	moveq #0,%d0
  42a6c2:	1003           	moveb %d3,%d0
  42a6c4:	2f00           	movel %d0,%sp@-
  42a6c6:	486f 0012      	pea %sp@(18)
  42a6ca:	2f0b           	movel %a3,%sp@-
  42a6cc:	4eb9 0042 e62e 	jsr 0x42e62e
  42a6d2:	4fef 000c      	lea %sp@(12),%sp
  42a6d6:	0803 0000      	btst #0,%d3
  42a6da:	6700 00e6      	beqw 0x42a7c2
  42a6de:	1c03           	moveb %d3,%d6
  42a6e0:	6076           	bras 0x42a758
  42a6e2:	7200           	moveq #0,%d1
  42a6e4:	1214           	moveb %a4@,%d1
  42a6e6:	0681 0044 c7e0 	addil #4507616,%d1
  42a6ec:	2041           	moveal %d1,%a0
  42a6ee:	1010           	moveb %a0@,%d0
  42a6f0:	0c00 000c      	cmpib #12,%d0
  42a6f4:	6346           	blss 0x42a73c
  42a6f6:	0c00 000d      	cmpib #13,%d0
  42a6fa:	672c           	beqs 0x42a728
  42a6fc:	0c00 000e      	cmpib #14,%d0
  42a700:	673a           	beqs 0x42a73c
  42a702:	0c00 000f      	cmpib #15,%d0
  42a706:	6738           	beqs 0x42a740
  42a708:	0c00 0010      	cmpib #16,%d0
  42a70c:	6732           	beqs 0x42a740
  42a70e:	0c00 0011      	cmpib #17,%d0
  42a712:	6730           	beqs 0x42a744
  42a714:	0c00 0012      	cmpib #18,%d0
  42a718:	6726           	beqs 0x42a740
  42a71a:	0c00 0013      	cmpib #19,%d0
  42a71e:	6730           	beqs 0x42a750
  42a720:	0c00 0014      	cmpib #20,%d0
  42a724:	672a           	beqs 0x42a750
  42a726:	6030           	bras 0x42a758
  42a728:	528c           	addql #1,%a4
  42a72a:	6002           	bras 0x42a72e
  42a72c:	528c           	addql #1,%a4
  42a72e:	b9ca           	cmpal %a2,%a4
  42a730:	6406           	bccs 0x42a738
  42a732:	0c14 009d      	cmpib #-99,%a4@
  42a736:	66f4           	bnes 0x42a72c
  42a738:	b9ca           	cmpal %a2,%a4
  42a73a:	671c           	beqs 0x42a758
  42a73c:	528c           	addql #1,%a4
  42a73e:	6018           	bras 0x42a758
  42a740:	568c           	addql #3,%a4
  42a742:	6014           	bras 0x42a758
  42a744:	528c           	addql #1,%a4
  42a746:	1014           	moveb %a4@,%d0
  42a748:	4600           	notb %d0
  42a74a:	cc00           	andb %d0,%d6
  42a74c:	548c           	addql #2,%a4
  42a74e:	6008           	bras 0x42a758
  42a750:	7000           	moveq #0,%d0
  42a752:	102c 0001      	moveb %a4@(1),%d0
  42a756:	d9c0           	addal %d0,%a4
  42a758:	b9ca           	cmpal %a2,%a4
  42a75a:	6406           	bccs 0x42a762
  42a75c:	0806 0000      	btst #0,%d6
  42a760:	6680           	bnes 0x42a6e2
  42a762:	0883 0000      	bclr #0,%d3
  42a766:	605a           	bras 0x42a7c2
  42a768:	528c           	addql #1,%a4
  42a76a:	1014           	moveb %a4@,%d0
  42a76c:	4600           	notb %d0
  42a76e:	c600           	andb %d0,%d3
  42a770:	7000           	moveq #0,%d0
  42a772:	1003           	moveb %d3,%d0
  42a774:	0280 0000 000c 	andil #12,%d0
  42a77a:	e498           	rorl #2,%d0
  42a77c:	7203           	moveq #3,%d1
  42a77e:	b081           	cmpl %d1,%d0
  42a780:	6230           	bhis 0x42a7b2
  42a782:	d040           	addw %d0,%d0
  42a784:	303b 0006      	movew %pc@(0x42a78c,%d0:w),%d0
  42a788:	4efb 0002      	jmp %pc@(0x42a78c,%d0:w)
  42a78c:	0008           	.short 0x0008
  42a78e:	0010 0018      	orib #24,%a0@
  42a792:	0020 2f6b      	orib #107,%a0@-
  42a796:	004e           	.short 0x004e
  42a798:	000e           	.short 0x000e
  42a79a:	6016           	bras 0x42a7b2
  42a79c:	2f6b 0052 000e 	movel %a3@(82),%sp@(14)
  42a7a2:	600e           	bras 0x42a7b2
  42a7a4:	2f6b 0056 000e 	movel %a3@(86),%sp@(14)
  42a7aa:	6006           	bras 0x42a7b2
  42a7ac:	2f6b 005a 000e 	movel %a3@(90),%sp@(14)
  42a7b2:	548c           	addql #2,%a4
  42a7b4:	600c           	bras 0x42a7c2
  42a7b6:	568c           	addql #3,%a4
  42a7b8:	6008           	bras 0x42a7c2
  42a7ba:	7000           	moveq #0,%d0
  42a7bc:	102c 0001      	moveb %a4@(1),%d0
  42a7c0:	d9c0           	addal %d0,%a4
  42a7c2:	ba6b 0014      	cmpw %a3@(20),%d5
  42a7c6:	6406           	bccs 0x42a7ce
  42a7c8:	b9ca           	cmpal %a2,%a4
  42a7ca:	6500 fafa      	bcsw 0x42a2c6
  42a7ce:	b9ca           	cmpal %a2,%a4
  42a7d0:	6600 0096      	bnew 0x42a868
  42a7d4:	42a7           	clrl %sp@-
  42a7d6:	302f 0008      	movew %sp@(8),%d0
  42a7da:	9047           	subw %d7,%d0
  42a7dc:	7200           	moveq #0,%d1
  42a7de:	3200           	movew %d0,%d1
  42a7e0:	2001           	movel %d1,%d0
  42a7e2:	2f00           	movel %d0,%sp@-
  42a7e4:	302b 0010      	movew %a3@(16),%d0
  42a7e8:	d045           	addw %d5,%d0
  42a7ea:	7200           	moveq #0,%d1
  42a7ec:	3200           	movew %d0,%d1
  42a7ee:	2001           	movel %d1,%d0
  42a7f0:	2f00           	movel %d0,%sp@-
  42a7f2:	302b 000e      	movew %a3@(14),%d0
  42a7f6:	d047           	addw %d7,%d0
  42a7f8:	7200           	moveq #0,%d1
  42a7fa:	3200           	movew %d0,%d1
  42a7fc:	2001           	movel %d1,%d0
  42a7fe:	2f00           	movel %d0,%sp@-
  42a800:	204f           	moveal %sp,%a0
  42a802:	2f28 001e      	movel %a0@(30),%sp@-
  42a806:	4eb9 0042 1cf4 	jsr 0x421cf4
  42a80c:	42af 0026      	clrl %sp@(38)
  42a810:	4878 0020      	pea 0x20
  42a814:	486f 002a      	pea %sp@(42)
  42a818:	204f           	moveal %sp,%a0
  42a81a:	2f28 002a      	movel %a0@(42),%sp@-
  42a81e:	4eb9 0042 bece 	jsr 0x42bece
  42a824:	4fef 0020      	lea %sp@(32),%sp
  42a828:	da6f 0014      	addw %sp@(20),%d5
  42a82c:	6034           	bras 0x42a862
  42a82e:	42a7           	clrl %sp@-
  42a830:	7000           	moveq #0,%d0
  42a832:	302f 0008      	movew %sp@(8),%d0
  42a836:	2f00           	movel %d0,%sp@-
  42a838:	302b 0010      	movew %a3@(16),%d0
  42a83c:	d045           	addw %d5,%d0
  42a83e:	7200           	moveq #0,%d1
  42a840:	3200           	movew %d0,%d1
  42a842:	2001           	movel %d1,%d0
  42a844:	2f00           	movel %d0,%sp@-
  42a846:	7000           	moveq #0,%d0
  42a848:	302b 000e      	movew %a3@(14),%d0
  42a84c:	2f00           	movel %d0,%sp@-
  42a84e:	204f           	moveal %sp,%a0
  42a850:	2f28 001e      	movel %a0@(30),%sp@-
  42a854:	4eb9 0042 1cf4 	jsr 0x421cf4
  42a85a:	4fef       	lea %sp@(20),%sp
