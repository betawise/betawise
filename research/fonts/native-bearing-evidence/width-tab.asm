
Neo 3.21 memory dump (base 0x420000):     file format binary


Disassembly of section .data:

0042bece <.data+0xbece>:
  42bece:	2f0b           	movel %a3,%sp@-
  42bed0:	226f 0008      	moveal %sp@(8),%a1
  42bed4:	266f 000c      	moveal %sp@(12),%a3
  42bed8:	200b           	movel %a3,%d0
  42beda:	670c           	beqs 0x42bee8
  42bedc:	7000           	moveq #0,%d0
  42bede:	1011           	moveb %a1@,%d0
  42bee0:	2213           	movel %a3@,%d1
  42bee2:	b280           	cmpl %d0,%d1
  42bee4:	6402           	bccs 0x42bee8
  42bee6:	2680           	movel %d0,%a3@
  42bee8:	4aa9 0004      	tstl %a1@(4)
  42beec:	6608           	bnes 0x42bef6
  42beee:	4240           	clrw %d0
  42bef0:	1029 0001      	moveb %a1@(1),%d0
  42bef4:	6010           	bras 0x42bf06
  42bef6:	2069 0004      	moveal %a1@(4),%a0
  42befa:	7000           	moveq #0,%d0
  42befc:	102f 0013      	moveb %sp@(19),%d0
  42bf00:	d1c0           	addal %d0,%a0
  42bf02:	4240           	clrw %d0
  42bf04:	1010           	moveb %a0@,%d0
  42bf06:	265f           	moveal %sp@+,%a3
  42bf08:	4e75           	rts
  42bf0a:	48e7 2300      	moveml %d2/%d6-%d7,%sp@-
  42bf0e:	5d8f           	subql #6,%sp
  42bf10:	4878 004d      	pea 0x4d
  42bf14:	42a7           	clrl %sp@-
  42bf16:	204f           	moveal %sp,%a0
  42bf18:	2f28 001e      	movel %a0@(30),%sp@-
  42bf1c:	61b0           	bsrs 0x42bece
  42bf1e:	4fef 000c      	lea %sp@(12),%sp
  42bf22:	7e00           	moveq #0,%d7
  42bf24:	3e00           	movew %d0,%d7
  42bf26:	2007           	movel %d7,%d0
  42bf28:	e548           	lslw #2,%d0
  42bf2a:	3c00           	movew %d0,%d6
  42bf2c:	dc47           	addw %d7,%d6
  42bf2e:	3006           	movew %d6,%d0
  42bf30:	7200           	moveq #0,%d1
  42bf32:	322f 001c      	movew %sp@(28),%d1
  42bf36:	7400           	moveq #0,%d2
  42bf38:	3406           	movew %d6,%d2
  42bf3a:	2f41 0002      	movel %d1,%sp@(2)
  42bf3e:	2202           	movel %d2,%d1
  42bf40:	3e80           	movew %d0,%sp@
  42bf42:	202f 0002      	movel %sp@(2),%d0
  42bf46:	4eb9 0043 70ee 	jsr 0x4370ee
  42bf4c:	9157           	subw %d0,%sp@
  42bf4e:	3017           	movew %sp@,%d0
  42bf50:	5c8f           	addql #6,%sp
  42bf52:	4cdf 00c4      	moveml %sp@+,%d2/%d6-%d7
  42bf56:	4e75           	rts
  42bf58:	48e7 0718      	moveml %d5-%d7/%a3-%a4,%sp@-
  42bf5c:	286f 0018      	moveal %sp@(24),%a4
  42bf60:	2a2f       	movel %sp@(28),%d5
