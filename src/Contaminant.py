class Contaminant:
    def __init__(self, source_id, ra, dec, phot_g_mean_mag, sep_arcsec):
        self.source_id = source_id
        self.ra = ra
        self.dec = dec
        self.phot_g_mean_mag = phot_g_mean_mag
        self.sep_arcsec = sep_arcsec

