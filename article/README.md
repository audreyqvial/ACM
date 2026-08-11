# ACM article draft

Files:

- `acm_article.tex`: complete English LaTeX draft.
- `references.bib`: initial bibliography scaffold; entries marked for verification must be checked before submission.

Compile with:

```bash
pdflatex acm_article.tex
bibtex acm_article
pdflatex acm_article.tex
pdflatex acm_article.tex
```

Required updates before submission:

1. Author, affiliation, email, and repository URL.
2. Regenerated CrewAI Flow+Crew preservation metrics.
3. Complete and independently verified bibliography.
4. Exact environment and benchmark hardware.
5. Removal of all TODO markers.
