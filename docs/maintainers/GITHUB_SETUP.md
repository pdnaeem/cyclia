# GitHub repository settings (About box)

Open the repository page, click the gear icon next to **About**, and paste these.

## Description (max 350 characters)

Cyclia: free, open-source LCA software (life cycle assessment) for Windows, macOS and Linux. ISO 14040/14044 study without programming, ecoinvent with your licence, your own data, EPD (EN 15804+A2), ISO 14067 carbon footprint, Monte Carlo, life cycle costing, MFA. Checked against ecoinvent and Brightway.

## Website

https://pdnaeem.github.io/cyclia/

## Topics

GitHub allows 20 topics. Type each one and press space or Enter.

```
life-cycle-assessment lca lca-software iso-14044 ecoinvent carbon-footprint epd en15804 environmental-footprint pef sustainability life-cycle-costing circular-economy material-flow-analysis social-lca monte-carlo environmental-science open-science desktop-app openlca-alternative
```

## Social preview

Settings > General > Social preview: upload `.github/social-preview.png`.

## Website on GitHub Pages (once)

1. Settings > Pages > Build and deployment: Source "Deploy from a branch", branch `main`, folder `/docs`, Save.
2. After a few minutes the site is at https://pdnaeem.github.io/cyclia/. The landing page is `docs/index.html`; the
   Markdown documents are published as pages with their own titles and descriptions (`docs/_config.yml`), and
   `sitemap.xml` is created automatically.
3. Check that https://pdnaeem.github.io/cyclia/sitemap.xml opens and lists the home page and the guide.

## Getting Cyclia into search results

A new site is not found until search engines know it exists. Without these steps, Google may take months to find it
on its own.

1. **Google Search Console** (https://search.google.com/search-console):
   - Add property > URL prefix `https://pdnaeem.github.io/cyclia/`.
   - Verify with **HTML file**: download the file (`google1234abcd.html`) into `docs/`, commit, push, wait two
     minutes, then press Verify.
   - Sitemaps: submit `sitemap.xml`.
   - URL inspection: paste `https://pdnaeem.github.io/cyclia/` and press **Request indexing**. Do the same for
     `USER_GUIDE.html` and `VALIDATION_ECOINVENT.html`.
2. **Bing Webmaster Tools** (https://www.bing.com/webmasters): import the site from Google Search Console, or
   verify with `BingSiteAuth.xml` in `docs/`. Bing also feeds DuckDuckGo, Ecosia and Yahoo.
3. **Links from places search engines already trust.** These help most:
   - the **Website** field of the GitHub About box (above);
   - the **Zenodo** record: Related identifiers > "is documented by" `https://pdnaeem.github.io/cyclia/`;
   - your **LinkedIn** profile (Featured and a post with a screenshot), ResearchGate and your university profile;
   - **Open Sustainable Technology** (https://github.com/protontypes/open-sustainable-technology): a pull request
     adding Cyclia under life cycle assessment;
   - AlternativeTo (add Cyclia as an alternative to openLCA and SimaPro), and answers in LCA forums where Cyclia
     solves the question asked.
4. **Use the same name everywhere:** "Cyclia" with "LCA software" or "life cycle assessment", so that a search for
   "Cyclia LCA" finds the site and the repository.
5. After two to four weeks, Search Console > Performance shows the searches that find Cyclia. A search for
   `site:pdnaeem.github.io/cyclia` shows the pages Google has indexed.

## Discussions (once)

Settings > General > Features: tick **Discussions**. The app's user guide and `SUPPORT.md` link to it.

## Release title for 1.9.1

Cyclia 1.9.1: LCIA import and identifier checks, and the ecoinvent 3.13 benchmark of 46 methods

Paste the text of `docs/releases/RELEASE_NOTES_v1.9.1.md` as the release description. GitHub has 1.8.2: the zip of
1.9.1 holds 1.8.3, 1.8.4 and 1.9.0 as well, and each has its own release notes in docs/releases.
