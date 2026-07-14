<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Reproduce the paper results

[English](REPRODUCE_PAPER_RESULT.md) · [Italiano](REPRODUCE_PAPER_RESULT_IT.md)

This beginner guide starts with a Gaia DR3 catalogue download, runs the PHOTO-CAT pipeline, and creates the coordinated contamination plots through the graphical interface.

## What this procedure reproduces

The procedure creates the current PHOTO-CAT result JSON and these publication products:

- contaminant-count distribution;
- angular-separation distribution;
- RA/Dec contamination sky map;
- a JSON manifest containing settings, paths, checksums, and the PHOTO-CAT version.

Exact agreement with a published table or statistic additionally requires the same PHOTO-CAT release, Gaia release, target selection, aperture, magnitude contrast, and configuration used for that analysis. The ADQL queries below apply only the stated Gaia G-magnitude selections; they do not add astrometric or photometric quality cuts.

## Before starting

You need:

- a current PHOTO-CAT release extracted to a writable folder;
- Python prepared through `START_WINDOWS.bat` or `START_UNIX.sh`;
- sufficient free disk space and memory;
- a web browser and access to the [official Gaia ESA Archive](https://gea.esac.esa.int/archive/).

The all-sky `0 <= phot_g_mean_mag <= 17` selection can be very large. Use an asynchronous Gaia Archive job. A registered Gaia account is strongly recommended for a long query because it makes job recovery and later downloads easier. The Archive currently warns that service instability or timeouts can occur while it evolves toward Gaia DR4.

Do not open and resave the downloaded catalogue with spreadsheet software unless you can guarantee that 64-bit `source_id` values remain exact. Scientific notation or rounding can prevent target matching.

## Part 1 — Download Gaia DR3 data

### 1. Open the Gaia Archive

1. Open [gea.esac.esa.int/archive](https://gea.esac.esa.int/archive/).
2. Sign in, or create an account if you want the long-running job saved in your workspace.
3. Open the search/query area and choose the advanced ADQL interface. Interface wording may change slightly; look for **Advanced (ADQL)** or an equivalent option.

Gaia DR3 documentation lists `gaiadr3.gaia_source` as the main source catalogue and provides tutorials for ADQL and advanced Archive use.

### 2. Prepare the G=17 neighbour-catalogue query

Use this query:

```sql
SELECT gaia.source_id,
       gaia.ra,
       gaia.dec,
       gaia.phot_g_mean_mag,
       gaia.parallax,
       gaia.parallax_error
FROM gaiadr3.gaia_source AS gaia
WHERE phot_g_mean_mag BETWEEN 0 AND 17
```

Column purpose:

- `source_id`: unique Gaia DR3 source identifier;
- `ra`, `dec`: sky position in degrees;
- `phot_g_mean_mag`: mean Gaia G magnitude used by PHOTO-CAT;
- `parallax`, `parallax_error`: downloaded for analysis/provenance but not required by the default PHOTO-CAT contamination calculation.

### 3. Prepare the separate G=12 target query

The target list must not be the G=17 catalogue. Create a second Gaia query with the same columns and a G=12 limit:

```sql
SELECT gaia.source_id,
       gaia.ra,
       gaia.dec,
       gaia.phot_g_mean_mag,
       gaia.parallax,
       gaia.parallax_error
FROM gaiadr3.gaia_source AS gaia
WHERE phot_g_mean_mag BETWEEN 0 AND 12
```

The two files have different roles:

- G=17 is the deeper neighbour catalogue used to find possible contaminating sources;
- G=12 is the brighter target sample on which PHOTO-CAT performs the contamination check.

### 4. Run both queries asynchronously

1. Submit the G=17 job with a recognizable name such as `photo_cat_gaia_dr3_g0_g17`.
2. Select an asynchronous query/job if the Archive offers synchronous and asynchronous modes.
3. Submit the G=12 job as `photo_cat_gaia_dr3_g0_g12`.
4. Open the job list and wait for both jobs to become completed.
5. If either job fails or times out, retry later from a registered account. Do not silently add `TOP`, smaller sky regions, or other cuts if the goal is this exact selection; any change must be documented.

### 5. Download both CSV files

1. Open each completed job result.
2. Choose CSV as the download format.
3. Save the two files with distinct names:

   ```text
   gaia_dr3_g0_g17.csv
   gaia_dr3_g0_g12_targets.csv
   ```

4. If the Archive downloads compressed files such as `.csv.gz`, extract them to plain `.csv` files before selecting them in the GUI.
5. Move both CSV files into the PHOTO-CAT `data/` folder or another stable writable location.
6. Save the exact queries beside them as `gaia_dr3_g0_g17.adql` and `gaia_dr3_g0_g12_targets.adql`, and record the download date.

The first CSV row should contain at least:

```text
source_id,ra,dec,phot_g_mean_mag,parallax,parallax_error
```

Do not rename the four columns required by PHOTO-CAT unless you also change their mappings in the GUI.

## Part 2 — Configure PHOTO-CAT

### 6. Start the graphical interface

- Windows: double-click `START_WINDOWS.bat`.
- macOS/Linux: run `sh START_UNIX.sh` from the project folder.

Wait for dependency setup to finish and for the PHOTO-CAT configurator to open.

### 7. Select the catalogue

Open **Files & columns** and set:

- **Catalog CSV**: the downloaded `gaia_dr3_g0_g17.csv`;
- **Catalog Source ID column**: `source_id`;
- **Catalog RA column**: `ra`;
- **Catalog Dec column**: `dec`;
- **Catalog magnitude column**: `phot_g_mean_mag`.

The extra parallax columns can remain in the CSV. PHOTO-CAT reads only the configured columns needed by the index.

Selecting the catalogue can automatically fill the targets and output folders. Check every generated path before running.

### 8. Choose the targets

Set **Targets CSV** to the separate `gaia_dr3_g0_g12_targets.csv` and keep **Targets Source ID column** as `source_id`.

Do not use the G=17 catalogue as the target file. PHOTO-CAT must build neighbours from the deeper G=17 catalogue and evaluate only the brighter G=12 target sample. Using G=17 for both fields changes the target population and therefore changes the distributions.

### 9. Check search settings

Open **Search settings** and verify:

- **Max build radius** is equal to or greater than the intended aperture;
- **Query aperture radius** is the aperture represented by the desired result;
- **Outer influence radius** may exceed the build radius: the query recomputes
  neighbours from the catalog out to that radius for the requested targets only;
- **Delta magnitude** matches the analysis configuration;
- **Contamination weighting model** matches the analysis configuration.

Do not infer a paper aperture from the plot filename. Record the actual query aperture. The value entered later in **Publication plots → Aperture** is metadata for the result and must match the query that produced that JSON.

For a large Gaia CSV, keep **Use Dask for very large CSV files** enabled. Leave chunk/checkpoint values at their defaults unless you have tested alternatives on your hardware.

### 10. Check run options

Open **Run options** and enable:

- **Run build step**;
- **Run query step**.

The build creates the reusable neighbour index. The query creates the target-result JSON used by the plots.

### 11. Save and run

1. Click **Save and run pipeline**.
2. Confirm the dialog.
3. Keep the pipeline console open.
4. Wait for both stages to finish successfully.

Large all-sky runs can take a long time. Dynamic bars show startup, catalogue loading, index construction, target processing, and result saving. Temporary pauses do not necessarily indicate a frozen process; check that elapsed time or the activity bar continues to update.

The query result is written under:

```text
<index folder>/results/
```

Its associated metadata is written under:

```text
<index folder>/results/metadata/
```

## Part 3 — Create the paper-result plots

### 12. Open Publication plots

Return to the PHOTO-CAT GUI and open **Results → Publication plots**.

Set or verify:

- **Result JSON**: the newest JSON from the completed pipeline; the GUI normally fills it automatically;
- **Aperture, arcsec**: exactly the query aperture represented by that JSON;
- **Output directory**: a new folder such as `<result name>_publication_plots`;
- **Format**:
  - `png` for convenient viewing and manuscript raster images;
  - `pdf` for vector publication output;
  - `svg` for editable vector output;
- **DPI**: use `300` or the journal requirement for PNG. DPI has little practical effect on vector PDF/SVG geometry.

### 13. Click Run

Click **Run** in the Publication plots panel.

The Tool output console immediately shows an animated command row and elapsed time. Wait for exit code `0` and the saved output paths.

The output directory contains:

```text
contaminant_count_distribution.<format>
separation_distribution.<format>
contamination_sky_map.<format>
publication_plots_manifest.json
```

Plot meaning:

- **contaminant-count distribution**: number of targets for each selected-contaminant count;
- **separation distribution**: raw angular separations of selected contaminants in one-arcsecond bins;
- **sky map**: targets in RA/Dec, classified by contaminant count with a colourblind-safe palette;
- **manifest**: input checksum, output checksums, aperture, format, DPI, creation time, and PHOTO-CAT version.

Scientific plot labels remain in English regardless of the GUI language.

## Part 4 — Verify and archive the reproduction

Before sharing the result, keep:

- original Gaia downloads or a documented way to regenerate them;
- `gaia_dr3_g0_g17.adql`;
- `gaia_dr3_g0_g12_targets.adql`;
- G=17 neighbour-catalogue CSV and G=12 target CSV;
- `config.yaml` used by the run;
- `index_manifest.json`;
- result JSON and its metadata JSON;
- three generated plots;
- `publication_plots_manifest.json`;
- PHOTO-CAT version from `photo-cat --version`;
- Gaia download date and Gaia DR3 acknowledgement/citation.

The manifest checksums should be preserved with the plots. If a plot or result JSON is edited, its recorded checksum no longer matches.

## Equivalent command-line step

After the pipeline result exists, the GUI Run action is equivalent to:

```bash
photo-cat publication-plots path/to/result.json \
  --aperture-arcsec 47 \
  --output-dir path/to/result_publication_plots \
  --format png \
  --dpi 300
```

Replace `47` with the aperture actually used by the query. Do not use this example value if the result was produced with a different aperture.

## Common problems

### The Gaia job times out

Use an asynchronous job while signed in and retry when the Archive is less busy. Changing the query changes the selection and must be documented.

### PHOTO-CAT reports missing columns

Check the CSV header and the case-sensitive mappings. `ra` and `RA` are different names.

### Source IDs do not match

Use the original CSV. Spreadsheet software may round Gaia `source_id` values.

### The build is too large for the machine

Keep Dask enabled, close other memory-heavy applications, verify free disk space, and consider a machine suitable for an all-sky catalogue. A reduced catalogue is useful for learning but is not the same reproduction.

### Publication plots selected the wrong JSON

Browse to the intended file under `<index folder>/results/`. Confirm its aperture and settings from the corresponding metadata JSON before running the plot command.

## Official Gaia references

- [Gaia ESA Archive](https://gea.esac.esa.int/archive/)
- [Gaia DR3 Archive tutorials](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_archive/sec_cu9arch_tutorials/)
- [Gaia DR3 `gaia_source` data model](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html)
- [Gaia DR3 credit and citation instructions](https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/)
