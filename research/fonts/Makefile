.PHONY: review vector-review bdfs specimens smallcaps charset-card private-specimens italic-spacing alternatives lucida policy superscript-strikes documentation clean
.DEFAULT_GOAL := review

bdfs:
	+$(MAKE) -C ../../fonts bdfs

review: bdfs
	python3 review.py

vector-review: bdfs
	python3 vector_review.py $(if $(REVIEW_FLAGS),--flags "$(REVIEW_FLAGS)")

specimens: bdfs
	python3 specimens.py

smallcaps: bdfs
	python3 smallcaps_sources.py

charset-card: bdfs
	python3 render_smallcaps_charset.py

private-specimens: bdfs
	python3 build_private_fonts.py

italic-spacing: bdfs
	python3 italic_spacing.py

alternatives:
	python3 audit_smallcap_alternatives.py

lucida: smallcaps alternatives
	python3 compare_lucida_smallcaps.py

policy: bdfs
	python3 ../font-policy/audit_current.py
	python3 ../font-policy/specimens.py

clean:
	$(RM) -r build ../font-policy/build

superscript-strikes: bdfs
	python3 superscript_strikes.py

documentation:
	python3 documentation_specimens.py
