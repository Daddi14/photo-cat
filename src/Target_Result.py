class Target_Result:
    def __init__(self, source_id, ra, dec, phot_g_mean_mag, flux_fraction_extra, num_contaminants, contaminants):
        self.source_id = source_id
        self.ra = ra
        self.dec = dec
        self.phot_g_mean_mag = phot_g_mean_mag
        self.flux_fraction_extra = flux_fraction_extra
        self.num_contaminants = num_contaminants
        self.contaminants = contaminants

