# Papers

PDFs in this folder are served as-is at `https://ruiminao.com/papers/<filename>`.
No Jekyll configuration is involved: anything placed here is copied straight to the site.

| File | Public URL |
|---|---|
| `Ao_JMP.pdf` | https://ruiminao.com/papers/Ao_JMP.pdf |

## Updating a paper

1. Compile the new version of the paper.
2. Copy the PDF into this folder, overwriting the old one. Keep the filename
   exactly the same so existing links in the CV, emails and applications keep working.
   ```powershell
   Copy-Item "<path-to-new-draft>.pdf" papers\Ao_JMP.pdf
   ```
3. Commit and push:
   ```powershell
   git add papers/Ao_JMP.pdf
   git commit -m "Update job market paper"
   git push
   ```
4. GitHub Pages rebuilds within a minute or two. Hard-refresh the URL
   (Ctrl+F5) if the browser still shows the old version.

## Adding a new paper

1. Drop the PDF here with a short, stable filename and no spaces,
   for example `Ao_DiscountStores.pdf`.
2. Add a row to the table above.
3. Link it from `research.md` with `[PDF](/papers/Ao_DiscountStores.pdf)`.
4. Commit and push as above.

## Notes

- Filenames are case-sensitive on the server. `Ao_JMP.pdf` and `ao_jmp.pdf` are different URLs.
- Keep files under about 50 MB. GitHub rejects anything over 100 MB.
- To check locally before pushing, run `bundle exec jekyll serve` and open
  `http://localhost:4000/papers/Ao_JMP.pdf`.
- This README is excluded from the built site via `exclude:` in `_config.yml`,
  so it never appears on ruiminao.com.
