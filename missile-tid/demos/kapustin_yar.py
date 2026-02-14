"""
Plot data from the Kapustin Yar region on January 8, 2026.
Analyzes the one-hour period following 23:20 Kyiv time (21:20 UTC).
"""
import argparse
import logging
from pathlib import Path
from typing import Optional

from laika import AstroDog

from tid import plot, util, scenario
from tid.config import Configuration

logger = logging.getLogger(__name__)

# load configuration data
conf = Configuration()


def main(output_path: Optional[Path] = None):
    # create our helpful astro dog
    dog = AstroDog(cache_dir=conf.cache_dir)

    # January 8, 2026 — 23:20 Kyiv time (EET, UTC+2) = 21:20 UTC
    date = util.datetime_fromstr("2026-01-08")

    # IGS stations in the Eastern Europe / Western Asia / Caucasus region
    # accessible via CDDIS (NASA Earthdata). Covers a broad area around
    # Kapustin Yar (48.6°N, 45.8°E) including stations in Turkey, Ukraine,
    # Romania, Bulgaria, Greece, Israel, Poland, Hungary, Germany, Russia,
    # Armenia, and Iran for maximum ionospheric coverage.
    # fmt: off
    eur_stations = [
        # Russia / Caucasus
        "zeck", "mdvj", "artu",
        # Ukraine
        "glsv", "polv",
        # Turkey
        "ankr", "ista", "tubi",
        # Armenia / Georgia
        "nssp",
        # Romania / Bulgaria / N. Macedonia
        "bucu", "sofi", "orid",
        # Greece / Cyprus
        "dyng", "pat0", "nico",
        # Israel
        "drag", "ramo",
        # Iran
        "tehn",
        # Hungary / Austria
        "penc", "graz",
        # Poland
        "bor1", "joze", "lama", "wroc",
        # Germany
        "wtzr", "wtza", "pots",
        # Italy
        "mate", "not1",
        # Czech / Slovakia
        "gope",
        # Finland / Scandinavia (northern coverage)
        "mets",
        # Spain / France (western reach for broader baseline)
        "tlse",
    ]
    # fmt: on

    logger.info("Starting scenario (downloading files, etc)")
    sc = scenario.Scenario.from_daterange(date, 1 * util.DAYS, eur_stations, dog)

    logger.info("Downloading complete, creating connections")
    sc.make_connections()

    logger.info("Connections created, resolving biases")
    sc.solve_biases()

    logger.info("Preparing animation")
    # Map extent centered on Kapustin Yar region:
    # West 25°E (Romania) to East 60°E (W. Kazakhstan)
    # South 30°N (Israel/Iran) to North 58°N (central Russia)
    extent = (25, 60, 30, 58)

    # 23:20 Kyiv = 21:20 UTC = ~frame 2133 at ~100 frames/hour over a full day
    # One hour window with slight padding on both ends
    anim = plot.plot_map(sc, extent=extent, frames=range(2120, 2240))

    if output_path:
        logger.info(f"Saving animation to {output_path}")
        plot.save_plot(anim, "kapustin_yar", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o", "--output-path", help="The directory in which to save plots", type=Path
    )
    parser.add_argument("-v", "--verbose", action="count")
    args = parser.parse_args()

    log_map = {0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}
    logging.basicConfig(
        level=log_map.get(args.verbose, conf.log_level),
        format="%(asctime)s [%(filename)s:%(lineno)d][%(levelname)s] %(message)s",
        datefmt=conf.logging.get("datefmt", "%Y-%m-%d %H:%M:%S"),
    )
    logging.getLogger("matplotlib.font_manager").disabled = True

    # Default to configuration values if none specified at command line
    if (output_path := args.output_path) is None:
        output_path = Path("demos/outputs")

    # Check if output path exists first
    if not output_path.exists():
        output_path.mkdir()

    main(output_path)
