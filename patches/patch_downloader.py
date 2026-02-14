"""
patch_downloader.py — Surgical patch for laika's downloader.py

Modifies only three things in the installed file:
  1. Adds CDDIS_OBS_BASE_URL constant after existing CDDIS constants
  2. Adds .netrc auth lines inside https_download_file()
  3. Replaces download_cors_station() with CDDIS fallback version

All other functions (download_orbits_russia_src, etc.) are preserved.
"""
import sys
import re


def patch(source: str) -> str:
    patched = source

    # ──────────────────────────────────────────────────────────────
    # PATCH 0: Ensure 'import logging' exists in the file
    # Just prepend it — Python handles duplicate imports fine
    # ──────────────────────────────────────────────────────────────
    if 'import logging' not in patched:
        patched = 'import logging\n' + patched
        print("  [0/4] Added 'import logging' at top of file")
    else:
        print("  [0/4] 'import logging' already present")

    # ──────────────────────────────────────────────────────────────
    # PATCH 1: Add CDDIS_OBS_BASE_URL constant
    # Insert after the last CDDIS_*_BASE_URL line
    # ──────────────────────────────────────────────────────────────
    if "CDDIS_OBS_BASE_URL" not in patched:
        # Find the last CDDIS_*_BASE_URL definition
        cddis_lines = list(re.finditer(
            r'^CDDIS_\w+_BASE_URL\s*=.*$', patched, re.MULTILINE
        ))
        if cddis_lines:
            insert_pos = cddis_lines[-1].end()
            new_const = (
                '\n\n# ── PATCH: direct CDDIS archive for IGS station observation data ──\n'
                '# Requires NASA Earthdata credentials in ~/.netrc\n'
                'CDDIS_OBS_BASE_URL = os.getenv("CDDIS_OBS_BASE_URL", '
                '"https://cddis.nasa.gov/archive/gnss/data/daily/")\n'
            )
            patched = patched[:insert_pos] + new_const + patched[insert_pos:]
            print("  [1/4] Added CDDIS_OBS_BASE_URL constant")
        else:
            print("  [1/4] WARNING: Could not find CDDIS_*_BASE_URL lines to anchor insertion")

    # ──────────────────────────────────────────────────────────────
    # PATCH 2: Add .netrc and cookie support in https_download_file
    # Insert after the CONNECTTIMEOUT line
    # ──────────────────────────────────────────────────────────────
    if "pycurl.NETRC" not in patched:
        # Find the CONNECTTIMEOUT line inside https_download_file
        match = re.search(
            r'(crl\.setopt\(pycurl\.CONNECTTIMEOUT,\s*\d+\))',
            patched
        )
        if match:
            insert_pos = match.end()
            netrc_lines = (
                '\n\n  # ── PATCH: enable .netrc auth for CDDIS / NASA Earthdata ──\n'
                '  crl.setopt(pycurl.NETRC, 1)  # use ~/.netrc when server asks for auth\n'
                '  crl.setopt(crl.COOKIEFILE, \'/tmp/cddis_cookies\')  # read cookies for OAuth redirects'
            )
            patched = patched[:insert_pos] + netrc_lines + patched[insert_pos:]
            print("  [2/4] Added .netrc authentication to https_download_file()")
        else:
            print("  [2/4] WARNING: Could not find CONNECTTIMEOUT line in https_download_file")

    # ──────────────────────────────────────────────────────────────
    # PATCH 3: Replace download_cors_station with CDDIS fallback
    # ──────────────────────────────────────────────────────────────
    # Find the function definition and replace it entirely
    # Match from "def download_cors_station" to the next "def " at column 0
    # or end of file
    func_pattern = re.compile(
        r'(def download_cors_station\(.*?\n)'  # function signature
        r'(.*?)'                                # function body
        r'(?=\ndef |\Z)',                       # until next top-level def or EOF
        re.DOTALL
    )
    match = func_pattern.search(patched)
    if match:
        new_func = '''def download_cors_station(time, station_name, cache_dir):
  import logging  # ensure logging is available regardless of top-level imports
  t = time.as_datetime()

  # ── Step 1: try US CORS servers (works for US stations like those
  #    used in the Vandenberg demo) ──
  cors_folder_path = t.strftime('%Y/%j/') + station_name + '/'
  cors_filename = station_name + t.strftime("%j0.%yd")
  url_bases_cors = (
    'https://geodesy.noaa.gov/corsdata/rinex/',
    'https://alt.ngs.noaa.gov/corsdata/rinex/',
  )
  try:
    filepath = download_and_cache_file(
      url_bases_cors, cors_folder_path,
      cache_dir + 'cors_obs/', cors_filename, compression='.gz'
    )
    return filepath
  except DownloadFailed:
    logging.info(
      f"Station {station_name} not found on US CORS, trying CDDIS..."
    )

  # ── Step 2: try NASA CDDIS archive (all ~530 IGS stations worldwide,
  #    requires Earthdata credentials in ~/.netrc) ──
  cddis_folder_path = t.strftime('%Y/%j/%yd/')
  cddis_filename = station_name + t.strftime("%j0.%yd")
  cddis_compression = '.gz' if t.year >= 2021 else '.Z'
  url_bases_cddis = (CDDIS_OBS_BASE_URL,)
  try:
    filepath = download_and_cache_file(
      url_bases_cddis, cddis_folder_path,
      cache_dir + 'cors_obs/', cddis_filename, compression=cddis_compression
    )
    return filepath
  except DownloadFailed:
    pass

  # If .gz failed, also try .Z
  if cddis_compression == '.gz':
    try:
      filepath = download_and_cache_file(
        url_bases_cddis, cddis_folder_path,
        cache_dir + 'cors_obs/', cddis_filename, compression='.Z'
      )
      return filepath
    except DownloadFailed:
      pass

  logging.warning(
    f"Station {station_name} not downloaded from CORS or CDDIS. "
    f"Check station name/date and ~/.netrc credentials."
  )
  return None

'''
        patched = patched[:match.start()] + new_func + patched[match.end():]
        print("  [3/4] Replaced download_cors_station() with CDDIS fallback version")
    else:
        print("  [3/4] WARNING: Could not find download_cors_station function")

    return patched


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path/to/downloader.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Reading {filepath}...")

    with open(filepath, "r") as f:
        original = f.read()

    result = patch(original)

    with open(filepath, "w") as f:
        f.write(result)

    print(f"Wrote patched file to {filepath}")
