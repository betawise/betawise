
Neo 3.21 memory dump (base 0x420000):     file format binary


Disassembly of section .data:

00421a82 <.data+0x1a82>:
  421a82:	48e7 233a      	moveml %d2/%d6-%d7/%a2-%a4/%fp,%sp@-
  421a86:	598f           	subql #4,%sp
  421a88:	1c2f 0033      	moveb %sp@(51),%d6
  421a8c:	13fc 0001 0000 	moveb #1,0x5c77
  421a92:	5c77 
  421a94:	247c 0000 5c72 	moveal #23666,%a2
  421a9a:	34af 002a      	movew %sp@(42),%a2@
  421a9e:	2c7c 0000 5c74 	moveal #23668,%fp
  421aa4:	3caf 002e      	movew %sp@(46),%fp@
  421aa8:	287c 0000 5c68 	moveal #23656,%a4
  421aae:	267c 0000 5c76 	moveal #23670,%a3
  421ab4:	4a13           	tstb %a3@
  421ab6:	6748           	beqs 0x421b00
  421ab8:	1013           	moveb %a3@,%d0
  421aba:	4400           	negb %d0
  421abc:	5200           	addqb #1,%d0
  421abe:	1680           	moveb %d0,%a3@
  421ac0:	4878 0002      	pea 0x2
  421ac4:	42a7           	clrl %sp@-
  421ac6:	2054           	moveal %a4@,%a0
  421ac8:	4240           	clrw %d0
  421aca:	1010           	moveb %a0@,%d0
  421acc:	7200           	moveq #0,%d1
  421ace:	3200           	movew %d0,%d1
  421ad0:	2001           	movel %d1,%d0
  421ad2:	2f00           	movel %d0,%sp@-
  421ad4:	4878 0002      	pea 0x2
  421ad8:	7000           	moveq #0,%d0
  421ada:	3016           	movew %fp@,%d0
  421adc:	2f00           	movel %d0,%sp@-
  421ade:	4a52           	tstw %a2@
  421ae0:	6608           	bnes 0x421aea
  421ae2:	7000           	moveq #0,%d0
  421ae4:	3012           	movew %a2@,%d0
  421ae6:	2f00           	movel %d0,%sp@-
  421ae8:	600e           	bras 0x421af8
  421aea:	303c ffff      	movew #-1,%d0
  421aee:	d052           	addw %a2@,%d0
  421af0:	7200           	moveq #0,%d1
  421af2:	3200           	movew %d0,%d1
  421af4:	2001           	movel %d1,%d0
  421af6:	2f00           	movel %d0,%sp@-
  421af8:	6100 f126      	bsrw 0x420c20
  421afc:	4fef 0018      	lea %sp@(24),%sp
  421b00:	28af 0024      	movel %sp@(36),%a4@
  421b04:	2054           	moveal %a4@,%a0
  421b06:	4aa8 0008      	tstl %a0@(8)
  421b0a:	6622           	bnes 0x421b2e
  421b0c:	2028 000c      	movel %a0@(12),%d0
  421b10:	7200           	moveq #0,%d1
  421b12:	1228 0002      	moveb %a0@(2),%d1
  421b16:	7400           	moveq #0,%d2
  421b18:	1406           	moveb %d6,%d2
  421b1a:	2e80           	movel %d0,%sp@
  421b1c:	2002           	movel %d2,%d0
  421b1e:	c141           	exg %d0,%d1
  421b20:	4eb9 0043 8378 	jsr 0x438378
  421b26:	c141           	exg %d0,%d1
  421b28:	d297           	addl %sp@,%d1
  421b2a:	2641           	moveal %d1,%a3
  421b2c:	6018           	bras 0x421b46
  421b2e:	2028 000c      	movel %a0@(12),%d0
  421b32:	2268 0008      	moveal %a0@(8),%a1
  421b36:	7200           	moveq #0,%d1
  421b38:	1206           	moveb %d6,%d1
  421b3a:	d281           	addl %d1,%d1
  421b3c:	d3c1           	addal %d1,%a1
  421b3e:	7200           	moveq #0,%d1
  421b40:	3211           	movew %a1@,%d1
  421b42:	d081           	addl %d1,%d0
  421b44:	2640           	moveal %d0,%a3
  421b46:	2054           	moveal %a4@,%a0
  421b48:	4aa8 0004      	tstl %a0@(4)
  421b4c:	6606           	bnes 0x421b54
  421b4e:	1e28 0001      	moveb %a0@(1),%d7
  421b52:	600c           	bras 0x421b60
  421b54:	2268 0004      	moveal %a0@(4),%a1
  421b58:	7000           	moveq #0,%d0
  421b5a:	1006           	moveb %d6,%d0
  421b5c:	d3c0           	addal %d0,%a1
  421b5e:	1e11           	moveb %a1@,%d7
  421b60:	4a2f 0037      	tstb %sp@(55)
  421b64:	6734           	beqs 0x421b9a
  421b66:	4878 0004      	pea 0x4
  421b6a:	2f0b           	movel %a3,%sp@-
  421b6c:	2054           	moveal %a4@,%a0
  421b6e:	4240           	clrw %d0
  421b70:	1010           	moveb %a0@,%d0
  421b72:	7200           	moveq #0,%d1
  421b74:	3200           	movew %d0,%d1
  421b76:	2001           	movel %d1,%d0
  421b78:	2f00           	movel %d0,%sp@-
  421b7a:	4240           	clrw %d0
  421b7c:	1007           	moveb %d7,%d0
  421b7e:	7200           	moveq #0,%d1
  421b80:	3200           	movew %d0,%d1
  421b82:	2f01           	movel %d1,%sp@-
  421b84:	7000           	moveq #0,%d0
  421b86:	3016           	movew %fp@,%d0
  421b88:	2f00           	movel %d0,%sp@-
  421b8a:	7000           	moveq #0,%d0
  421b8c:	3012           	movew %a2@,%d0
  421b8e:	2f00           	movel %d0,%sp@-
  421b90:	6100 f08e      	bsrw 0x420c20
  421b94:	4fef 0018      	lea %sp@(24),%sp
  421b98:	602e           	bras 0x421bc8
  421b9a:	2f0b           	movel %a3,%sp@-
  421b9c:	2054           	moveal %a4@,%a0
  421b9e:	4240           	clrw %d0
  421ba0:	1010           	moveb %a0@,%d0
  421ba2:	7200           	moveq #0,%d1
  421ba4:	3200           	movew %d0,%d1
  421ba6:	2001           	movel %d1,%d0
  421ba8:	2f00           	movel %d0,%sp@-
  421baa:	4240           	clrw %d0
  421bac:	1007           	moveb %d7,%d0
  421bae:	7200           	moveq #0,%d1
  421bb0:	3200           	movew %d0,%d1
  421bb2:	2f01           	movel %d1,%sp@-
  421bb4:	7000           	moveq #0,%d0
  421bb6:	3016           	movew %fp@,%d0
  421bb8:	2f00           	movel %d0,%sp@-
  421bba:	7000           	moveq #0,%d0
  421bbc:	3012           	movew %a2@,%d0
  421bbe:	2f00           	movel %d0,%sp@-
  421bc0:	6100 ea1c      	bsrw 0x4205de
  421bc4:	4fef 0014      	lea %sp@(20),%sp
  421bc8:	4239 0000 5c77 	clrb 0x5c77
  421bce:	588f           	addql #4,%sp
  421bd0:	4cdf 5cc4      	moveml %sp@+,%d2/%d6-%d7/%a2-%a4/%fp
  421bd4:	4e75           	rts
