from django.db import models
from django.contrib.auth.models import AbstractUser


class Perusahaan(models.Model):
    nama = models.CharField(max_length=255)
    deskripsi = models.TextField(blank=True)
    batas_waktu_review = models.IntegerField(
        default=3,
        help_text="Batas waktu review dalam jam"
    )
    sharepoint_drive_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Drive ID SharePoint perusahaan ini"
    )

    def __str__(self):
        return self.nama


class Jabatan(models.Model):
    nama = models.CharField(max_length=100)
    deskripsi = models.TextField(blank=True)

    def __str__(self):
        return self.nama


class Pegawai(AbstractUser):

    nama = models.CharField(max_length=255)

    perusahaan = models.ForeignKey(
        Perusahaan,
        on_delete=models.CASCADE,
        null=True
    )

    jabatan = models.ForeignKey(
        Jabatan,
        on_delete=models.CASCADE,
        null=True
    )

    ROLE_CHOICES = (
        ('staff','Staff'),
        ('manager','Manager'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES
    )

    STATUS_PEGAWAI_CHOICES = (
        ('magang','Magang'),
        ('tetap','Tetap'),
        ('kontrak','Kontrak'),
    )

    status_pegawai = models.CharField(
        max_length=10,
        choices=STATUS_PEGAWAI_CHOICES,
        default='tetap'
    )

    STATUS_AKUN_CHOICES = (
        ('aktif','Aktif'),
        ('tidak_aktif','Tidak Aktif'),
    )

    status_akun = models.CharField(
        max_length=15,
        choices=STATUS_AKUN_CHOICES,
        default='aktif'
    )

    def __str__(self):
        return self.nama


class Project(models.Model):

    STATUS_CHOICES = (
        ('ongoing','Ongoing'),
        ('selesai','Selesai'),
    )

    STATUS_KONTRAK_CHOICES = (
        ('kontrak','Kontrak'),
        ('belum_kontrak','Belum Kontrak'),
    )

    nama = models.CharField(max_length=255)
    deskripsi = models.TextField()
    kode_pekerjaan = models.CharField(max_length=100, blank=True)
    daerah = models.CharField(max_length=255, blank=True)
    instansi = models.CharField(max_length=255, blank=True)

    mulai = models.DateField()
    akhir = models.DateField()

    perusahaan = models.ForeignKey(
        Perusahaan,
        on_delete=models.CASCADE
    )

    dibuat_oleh = models.ForeignKey(
        Pegawai,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ongoing'
    )

    status_kontrak = models.CharField(
        max_length=20,
        choices=STATUS_KONTRAK_CHOICES,
        default='belum_kontrak'
    )

    tanggal_selesai = models.DateTimeField(
        null=True,
        blank=True
    )

    perusahaan_administrasi = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.nama


class Kegiatan(models.Model):
    nama = models.CharField(max_length=255)
    deskripsi = models.TextField(blank=True)
    mulai = models.DateTimeField()
    akhir = models.DateTimeField()
    pegawai = models.ManyToManyField(
        Pegawai,
        related_name='kegiatan'
    )
    perusahaan = models.ForeignKey(
        Perusahaan,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    dibuat_oleh = models.ForeignKey(
        Pegawai,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kegiatan_dibuat'
    )

    def __str__(self):
        return self.nama


class Subproject(models.Model):

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE
    )

    nama = models.CharField(max_length=255)
    deskripsi = models.TextField()

    mulai = models.DateTimeField()
    akhir = models.DateTimeField()

    pegawai = models.ForeignKey(
        Pegawai,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    sharepoint_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path penyimpanan di SharePoint. Kosongkan untuk menggunakan path default."
    )

    def get_sharepoint_path(self):
        """Kembalikan path efektif: custom jika diisi, default jika kosong."""
        if self.sharepoint_path:
            return self.sharepoint_path.strip('/')
        return f"KPI_System/{self.project.nama}/{self.nama}"

    def __str__(self):
        return self.nama


class Tugas(models.Model):

    subproject = models.ForeignKey(
        Subproject,
        on_delete=models.CASCADE
    )

    nama_file = models.CharField(max_length=255)
    file_url = models.TextField()

    tgl_upload = models.DateTimeField()

    terlambat = models.CharField(
        max_length=10,
        choices=(
            ('Ya','Ya'),
            ('Tidak','Tidak')
        )
    )


class Review(models.Model):

    STATUS_CHOICES = (
        ('revisi','Revisi'),
        ('selesai','Selesai'),
    )

    tugas = models.ForeignKey(
        Tugas,
        on_delete=models.CASCADE
    )

    tgl_revisi = models.DateTimeField()

    catatan = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )

    reviewer = models.ForeignKey(
        Pegawai,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )