from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.conf import settings
import requests
from django.utils import timezone
from django.utils.timezone import now
from .models import Pegawai, Perusahaan, Jabatan, Project, Subproject, Tugas, Review, Kegiatan
from datetime import datetime
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from io import BytesIO
from django.utils.formats import date_format
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse
from django.utils.timezone import make_aware
from datetime import datetime, timedelta

# Create your views here.
def user_login(request):
    msg = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.status_akun == 'tidak_aktif':
                msg = 'Akun Anda tidak aktif.'
            else:
                login(request, user)
                return redirect('dashboard')
        else:
            msg = 'Username atau Password salah'
    return render(request, 'index.html', {'msg': msg})

def landing_page(request):
    return render(request, 'index.html')

@login_required
def dashboard(request):
    today = now().date()
    if request.user.is_superuser:
        upcoming_project = Project.objects.filter(mulai__gt=today).count()
        project_diproses = Project.objects.filter(
            status='ongoing',
            mulai__lte=today
        ).count()
        total_project = Project.objects.filter(status='selesai').count()
        total_pegawai = Pegawai.objects.count()
        perusahaan_list = Perusahaan.objects.all().order_by('nama')
    else:
        perusahaan = request.user.perusahaan
        upcoming_project = Project.objects.filter(
            mulai__gt=today,
            perusahaan=perusahaan
        ).count()
        project_diproses = Project.objects.filter(
            status='ongoing',
            mulai__lte=today,
            perusahaan=request.user.perusahaan
        ).count()
        total_project = Project.objects.filter(
            status='selesai',
            perusahaan=perusahaan
        ).count()
        total_pegawai = Pegawai.objects.filter(
            perusahaan=perusahaan
        ).count()
        perusahaan_list = None
    context = {
        'upcoming_project': upcoming_project,
        'project_diproses': project_diproses,
        'total_project': total_project,
        'total_pegawai': total_pegawai,
        'perusahaan_list': perusahaan_list
    }
    return render(request,'dashboard.html',context)

@login_required
def calendar_events(request):
    perusahaan_id = request.GET.get('perusahaan_id')
    kategori = request.GET.get('kategori')
    events = []
    if kategori == "subproject":
        data = Subproject.objects.select_related('project','pegawai')
        if request.user.is_superuser:
            if perusahaan_id:
                data = data.filter(project__perusahaan_id=perusahaan_id)
        else:
            data = data.filter(project__perusahaan=request.user.perusahaan)
        for sub in data:
            events.append({
                "title": sub.nama,
                "start": sub.mulai.isoformat(),
                "end": sub.akhir.isoformat(),
                "kategori": "Subproject",
                "project": sub.project.nama,
                "pegawai": sub.pegawai.nama,
                "deskripsi": sub.deskripsi
            })
    else:
        data = Project.objects.select_related('perusahaan')
        if request.user.is_superuser:
            if perusahaan_id:
                data = data.filter(perusahaan_id=perusahaan_id)
        else:
            data = data.filter(perusahaan=request.user.perusahaan)
        for project in data:
            events.append({
                "title": project.nama,
                "start": project.mulai.isoformat(),
                "end": project.akhir.isoformat(),
                "kategori": "Project",
                "perusahaan": project.perusahaan.nama,
                "deskripsi": project.deskripsi
            })
    return JsonResponse(events, safe=False)

@login_required
def project(request):
    user = request.user
    today = now().date()

    if user.is_superuser:
        project_qs = Project.objects.select_related(
            'perusahaan', 'dibuat_oleh'
        ).all().order_by('status', '-mulai', 'nama')
    else:
        project_qs = Project.objects.select_related(
            'perusahaan', 'dibuat_oleh'
        ).filter(
            perusahaan=user.perusahaan
        ).order_by('status', '-mulai', 'nama')

    project_list = []
    for project in project_qs:
        terlambat_info = None

        if project.status == 'selesai':
            # Gunakan tanggal_selesai jika ada, fallback ke today
            tgl_selesai = project.tanggal_selesai.date() if project.tanggal_selesai else today
            if tgl_selesai > project.akhir:
                selisih = tgl_selesai - project.akhir
                terlambat_info = f"{selisih.days} Hari"

        elif project.status == 'ongoing' and project.akhir < today:
            selisih = today - project.akhir
            terlambat_info = f"{selisih.days} Hari"

        project_list.append({
            'project': project,
            'terlambat_info': terlambat_info,
        })

    perusahaan_list = Perusahaan.objects.all()
    context = {
        "project_list": project_list,
        "perusahaan_list": perusahaan_list
    }
    return render(request, "project.html", context)

@login_required
def tambah_project(request):
    if request.method == "POST":
        user = request.user
        if user.role != "manager":
            return JsonResponse({
                "message": "Anda tidak memiliki akses"
            }, status=403)
        nama = request.POST.get("nama")
        deskripsi = request.POST.get("deskripsi")
        mulai = request.POST.get("mulai")
        akhir = request.POST.get("akhir")
        kode_pekerjaan = request.POST.get("kode_pekerjaan")
        daerah = request.POST.get("daerah")
        instansi = request.POST.get("instansi")
        status_kontrak = request.POST.get("status_kontrak")
        perusahaan_administrasi = request.POST.get("perusahaan_administrasi")
        Project.objects.create(
            nama=nama,
            deskripsi=deskripsi,
            mulai=mulai,
            akhir=akhir,
            kode_pekerjaan=kode_pekerjaan,
            daerah=daerah,
            instansi=instansi,
            status_kontrak=status_kontrak,
            perusahaan_administrasi=perusahaan_administrasi,
            perusahaan=user.perusahaan,
            dibuat_oleh=user
        )
        return JsonResponse({
            "message":"Project berhasil ditambahkan"
        }, status=200)
    return JsonResponse({
        "message":"Invalid request"
    }, status=400)

@login_required
def edit_project(request):
    if request.method == "POST":
        user = request.user
        project_id = request.POST.get("id")
        project = get_object_or_404(Project, id=project_id)

        if user.is_superuser:
            # Superuser hanya bisa edit tanggal mulai, tanggal akhir, status
            project.mulai = request.POST.get("mulai")
            project.akhir = request.POST.get("akhir")
            status_baru = request.POST.get("status")
            if status_baru == 'selesai' and project.status != 'selesai':
                project.tanggal_selesai = now()
            elif status_baru == 'ongoing':
                project.tanggal_selesai = None
            project.status = status_baru
            project.save()
            return JsonResponse({"message": "Project berhasil diperbarui"}, status=200)

        if user.role != "manager":
            return JsonResponse({"message": "Anda tidak memiliki akses"}, status=403)

        if project.perusahaan != user.perusahaan:
            return JsonResponse({"message": "Anda tidak memiliki akses ke project ini"}, status=403)

        project.nama = request.POST.get("nama")
        project.deskripsi = request.POST.get("deskripsi")
        project.mulai = request.POST.get("mulai")
        project.akhir = request.POST.get("akhir")
        project.kode_pekerjaan = request.POST.get("kode_pekerjaan")
        project.daerah = request.POST.get("daerah")
        project.instansi = request.POST.get("instansi")
        project.status_kontrak = request.POST.get("status_kontrak")
        project.perusahaan_administrasi = request.POST.get("perusahaan_administrasi")

        status_baru = request.POST.get("status")
        if status_baru == 'selesai' and project.status != 'selesai':
            project.tanggal_selesai = now()
        elif status_baru == 'ongoing':
            project.tanggal_selesai = None
        project.status = status_baru
        project.save()
        return JsonResponse({"message": "Project berhasil diperbarui"}, status=200)
    return JsonResponse({"message": "Invalid request"}, status=400)


@login_required
def hapus_project(request,id):
    if request.method == "DELETE":
        project = get_object_or_404(Project,id=id)
        project.delete()
        return JsonResponse({'message':'Project berhasil dihapus!'},status=200)
    return JsonResponse({'error':'Invalid request method'},status=400)

@login_required
def kegiatan(request):
    user = request.user
    perusahaan_user = user.perusahaan
    if user.is_superuser:
        pegawai_list = Pegawai.objects.filter(
            is_superuser=False,
            status_akun='aktif'        # ← tambahan filter aktif
        ).order_by('nama')
        perusahaan_list = Perusahaan.objects.all().order_by('nama')
    else:
        pegawai_list = Pegawai.objects.filter(
            perusahaan=perusahaan_user,
            is_superuser=False,
            status_akun='aktif'        # ← tambahan filter aktif
        ).order_by('nama')
        perusahaan_list = None

    context = {
        'pegawai_list': pegawai_list,
        'perusahaan_list': perusahaan_list,
    }
    return render(request, 'kegiatan.html', context)

@login_required
def calendar_events_kegiatan(request):
    perusahaan_id = request.GET.get('perusahaan_id')
    user = request.user

    if user.is_superuser:
        if perusahaan_id:
            qs = Kegiatan.objects.filter(
                perusahaan_id=perusahaan_id
            ).prefetch_related('pegawai')
        else:
            qs = Kegiatan.objects.all().prefetch_related('pegawai')
    else:
        qs = Kegiatan.objects.filter(
            perusahaan=user.perusahaan
        ).prefetch_related('pegawai')

    events = []
    for k in qs:
        events.append({
            'id': k.id,
            'title': k.nama,
            'start': k.mulai.isoformat(),
            'end': k.akhir.isoformat(),
            'deskripsi': k.deskripsi,
            'pegawai': [p.nama for p in k.pegawai.all()],
        })
    return JsonResponse(events, safe=False)

@login_required
def tambah_kegiatan(request):
    if request.method == 'POST':
        user = request.user
        if user.role != 'manager' and not user.is_superuser:
            return JsonResponse(
                {'message': 'Anda tidak memiliki akses'},
                status=403
            )
        nama = request.POST.get('nama')
        deskripsi = request.POST.get('deskripsi')
        tanggal_mulai = request.POST.get('tanggal_mulai')
        jam_mulai = request.POST.get('jam_mulai')
        tanggal_akhir = request.POST.get('tanggal_akhir')
        jam_akhir = request.POST.get('jam_akhir')
        pegawai_ids = request.POST.getlist('pegawai')

        mulai = make_aware(datetime.strptime(
            f"{tanggal_mulai} {jam_mulai}", "%Y-%m-%d %H:%M"
        ))
        akhir = make_aware(datetime.strptime(
            f"{tanggal_akhir} {jam_akhir}", "%Y-%m-%d %H:%M"
        ))

        kegiatan = Kegiatan.objects.create(
            nama=nama,
            deskripsi=deskripsi,
            mulai=mulai,
            akhir=akhir,
            perusahaan=user.perusahaan,
            dibuat_oleh=user
        )
        kegiatan.pegawai.set(pegawai_ids)

        return JsonResponse(
            {'message': 'Kegiatan berhasil ditambahkan!'},
            status=200
        )
    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def edit_kegiatan(request):
    if request.method == 'POST':
        user = request.user
        if user.role != 'manager' and not user.is_superuser:
            return JsonResponse(
                {'message': 'Anda tidak memiliki akses'},
                status=403
            )
        kegiatan_id = request.POST.get('id')
        kegiatan = get_object_or_404(Kegiatan, id=kegiatan_id)

        nama = request.POST.get('nama')
        deskripsi = request.POST.get('deskripsi')
        tanggal_mulai = request.POST.get('tanggal_mulai')
        jam_mulai = request.POST.get('jam_mulai')
        tanggal_akhir = request.POST.get('tanggal_akhir')
        jam_akhir = request.POST.get('jam_akhir')
        pegawai_ids = request.POST.getlist('pegawai')

        mulai = make_aware(datetime.strptime(
            f"{tanggal_mulai} {jam_mulai}", "%Y-%m-%d %H:%M"
        ))
        akhir = make_aware(datetime.strptime(
            f"{tanggal_akhir} {jam_akhir}", "%Y-%m-%d %H:%M"
        ))

        kegiatan.nama = nama
        kegiatan.deskripsi = deskripsi
        kegiatan.mulai = mulai
        kegiatan.akhir = akhir
        kegiatan.save()
        kegiatan.pegawai.set(pegawai_ids)

        return JsonResponse(
            {'message': 'Kegiatan berhasil diperbarui!'},
            status=200
        )
    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def hapus_kegiatan(request, id):
    if request.method == 'DELETE':
        kegiatan = get_object_or_404(Kegiatan, id=id)
        kegiatan.delete()
        return JsonResponse(
            {'message': 'Kegiatan berhasil dihapus!'},
            status=200
        )
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def get_kegiatan_detail(request, id):
    kegiatan = get_object_or_404(Kegiatan, id=id)
    mulai_lokal = timezone.localtime(kegiatan.mulai)
    akhir_lokal = timezone.localtime(kegiatan.akhir)
    return JsonResponse({
        'id': kegiatan.id,
        'nama': kegiatan.nama,
        'deskripsi': kegiatan.deskripsi,
        'tanggal_mulai': mulai_lokal.strftime('%Y-%m-%d'),
        'jam_mulai': mulai_lokal.strftime('%H:%M'),
        'tanggal_akhir': akhir_lokal.strftime('%Y-%m-%d'),
        'jam_akhir': akhir_lokal.strftime('%H:%M'),
        'pegawai': list(
            kegiatan.pegawai.values_list('id', flat=True)
        ),
    })

@login_required
def subproject(request):
    user = request.user
    perusahaan_user = user.perusahaan

    # FILTER SUBPROJECT BERDASARKAN ROLE
    # Query list TIDAK difilter status_akun agar data lama tetap tampil
    if user.is_superuser:
        subproject_list = Subproject.objects.select_related(
            'project', 'pegawai'
        ).all()
    elif user.role == "manager":
        subproject_list = Subproject.objects.select_related(
            'project', 'pegawai'
        ).filter(
            project__perusahaan=perusahaan_user
        )
    else:  # staff
        subproject_list = Subproject.objects.select_related(
            'project', 'pegawai'
        ).filter(
            pegawai=user
        )
    subproject_list = subproject_list.order_by('-mulai', 'nama')

    # dropdown project (hanya perusahaan yg sama + ongoing)
    project_list = Project.objects.filter(
        perusahaan=perusahaan_user,
        status='ongoing'
    ).order_by('nama')

    # dropdown pegawai untuk TAMBAH — hanya yang aktif dan role staff
    pegawai_list = Pegawai.objects.filter(
        perusahaan=perusahaan_user,
        status_akun='aktif',
        role='staff'
    ).order_by('nama')

    # dropdown pegawai untuk EDIT — semua role staff (aktif maupun tidak)
    pegawai_list_edit = Pegawai.objects.filter(
        perusahaan=perusahaan_user,
        role='staff'
    ).order_by('nama')

    context = {
        'subproject_list': subproject_list,
        'project_list': project_list,
        'pegawai_list': pegawai_list,
        'pegawai_list_edit': pegawai_list_edit,   # ← tambahan
    }
    return render(request, 'subproject.html', context)

@login_required
def tambah_subproject(request):
    if request.method == "POST":
        nama = request.POST.get('nama')
        deskripsi = request.POST.get('deskripsi')
        tanggal_mulai = request.POST.get('tanggal_mulai')
        jam_mulai = request.POST.get('jam_mulai')
        tanggal_akhir = request.POST.get('tanggal_akhir')
        jam_akhir = request.POST.get('jam_akhir')
        project_id = request.POST.get('project')
        pegawai_id = request.POST.get('pegawai')
        sharepoint_path = request.POST.get('sharepoint_path', '').strip()

        project = get_object_or_404(Project, id=project_id)
        pegawai = get_object_or_404(Pegawai, id=pegawai_id)
        mulai = datetime.strptime(f"{tanggal_mulai} {jam_mulai}", "%Y-%m-%d %H:%M")
        akhir = datetime.strptime(f"{tanggal_akhir} {jam_akhir}", "%Y-%m-%d %H:%M")

        Subproject.objects.create(
            nama=nama,
            deskripsi=deskripsi,
            mulai=mulai,
            akhir=akhir,
            project=project,
            pegawai=pegawai,
            sharepoint_path=sharepoint_path if sharepoint_path else None
        )
        return JsonResponse({'message': 'SubProject berhasil ditambahkan!'}, status=200)
    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def edit_subproject(request):
    if request.method == "POST":
        subproject_id = request.POST.get('id')
        subproject = get_object_or_404(Subproject, id=subproject_id)
        nama = request.POST.get('nama')
        deskripsi = request.POST.get('deskripsi')
        tanggal_mulai = request.POST.get('tanggal_mulai')
        jam_mulai = request.POST.get('jam_mulai')
        tanggal_akhir = request.POST.get('tanggal_akhir')
        jam_akhir = request.POST.get('jam_akhir')
        sharepoint_path = request.POST.get('sharepoint_path', '').strip()

        mulai = make_aware(datetime.strptime(f"{tanggal_mulai} {jam_mulai}", "%Y-%m-%d %H:%M"))
        akhir = make_aware(datetime.strptime(f"{tanggal_akhir} {jam_akhir}", "%Y-%m-%d %H:%M"))

        subproject.nama = nama
        subproject.deskripsi = deskripsi
        subproject.mulai = mulai
        subproject.akhir = akhir
        subproject.project_id = request.POST.get('project')
        subproject.pegawai_id = request.POST.get('pegawai')
        subproject.sharepoint_path = sharepoint_path if sharepoint_path else None
        subproject.save()

        # Recalculate status terlambat semua tugas di subproject ini
        tugas_terkait = Tugas.objects.filter(subproject=subproject)
        for tugas in tugas_terkait:
            if tugas.tgl_upload > akhir:
                tugas.terlambat = "Ya"
            else:
                tugas.terlambat = "Tidak"
            tugas.save()

        return JsonResponse({'message': 'SubProject berhasil diupdate!'})
    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def hapus_subproject(request, id):
    if request.method == "DELETE":
        subproject = get_object_or_404(Subproject, id=id)
        subproject.delete()
        return JsonResponse({'message': 'SubProject berhasil dihapus!'}, status=200)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def get_access_token():
    url = f"https://login.microsoftonline.com/{settings.TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

@login_required
def tugas(request):
    user = request.user
    perusahaan_user = user.perusahaan
    if user.is_superuser:
        tugas_list = Tugas.objects.select_related(
            'subproject',
            'subproject__project',
            'subproject__pegawai'
        ).all()
    elif user.role == "manager":
        tugas_list = Tugas.objects.select_related(
            'subproject',
            'subproject__project',
            'subproject__pegawai'
        ).filter(
            subproject__project__perusahaan=perusahaan_user
        )
    else:  # staff
        tugas_list = Tugas.objects.select_related(
            'subproject',
            'subproject__project',
            'subproject__pegawai'
        ).filter(
            subproject__pegawai=user
        )
    tugas_list = tugas_list.order_by('-tgl_upload', 'subproject__nama')

    # Hitung selisih waktu untuk setiap tugas
    tugas_dengan_selisih = []
    for tugas in tugas_list:
        deadline = tugas.subproject.akhir
        upload = tugas.tgl_upload
        selisih = upload - deadline if tugas.terlambat == "Ya" else deadline - upload
        total_detik = int(selisih.total_seconds())
        hari = total_detik // 86400
        jam = (total_detik % 86400) // 3600
        menit = (total_detik % 3600) // 60

        if hari > 0:
            keterangan_waktu = f"{hari} hari {jam} jam {menit} menit"
        elif jam > 0:
            keterangan_waktu = f"{jam} jam {menit} menit"
        else:
            keterangan_waktu = f"{menit} menit"

        tugas_dengan_selisih.append({
            'tugas': tugas,
            'keterangan_waktu': keterangan_waktu,
        })

    pegawai_list = Pegawai.objects.filter(
        perusahaan=perusahaan_user
    ).order_by('nama')
    context = {
        "tugas_list": tugas_dengan_selisih,
        "pegawai_list": pegawai_list
    }
    return render(request, "tugas.html", context)

@login_required
def upload_tugas(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        subproject_id = request.POST.get("subproject")
        subproject = get_object_or_404(Subproject, id=subproject_id)

        # Ambil drive_id dari perusahaan pegawai yang upload
        perusahaan = request.user.perusahaan
        drive_id = perusahaan.sharepoint_drive_id

        if not drive_id:
            return JsonResponse({
                "message": "SharePoint perusahaan Anda belum dikonfigurasi. Hubungi administrator."
            }, status=400)

        # Gunakan path custom atau default
        path = subproject.get_sharepoint_path()

        token = get_access_token()
        upload_url = (
            f"https://graph.microsoft.com/v1.0/drives/"
            f"{drive_id}/root:/{path}/{file.name}:/content"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": file.content_type
        }
        response = requests.put(
            upload_url,
            headers=headers,
            data=file.read()
        )
        if response.status_code in [200, 201]:
            file_url = response.json().get("webUrl")
            tgl_upload = timezone.now()
            status_terlambat = "Ya" if tgl_upload > subproject.akhir else "Tidak"
            Tugas.objects.create(
                subproject=subproject,
                nama_file=file.name,
                file_url=file_url,
                tgl_upload=tgl_upload,
                terlambat=status_terlambat
            )
            return JsonResponse({"message": "File berhasil diupload!"}, status=200)
        else:
            return JsonResponse({"message": "Upload gagal!"}, status=400)
    return JsonResponse({"message": "Invalid request"}, status=400)

@login_required
def hapus_tugas(request, id):
    if request.method == "DELETE":
        tugas = get_object_or_404(Tugas, id=id)
        tugas.delete()
        return JsonResponse({
            "message": "Tugas berhasil dihapus!"
        }, status=200)
    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
def review_list(request):
    user = request.user
    perusahaan_user = user.perusahaan
    if user.is_superuser:
        review_qs = Review.objects.select_related(
            'tugas',
            'tugas__subproject',
            'tugas__subproject__project',
            'tugas__subproject__project__perusahaan',
            'reviewer'
        ).all()
    elif user.role == "manager":
        review_qs = Review.objects.select_related(
            'tugas',
            'tugas__subproject',
            'tugas__subproject__project',
            'tugas__subproject__project__perusahaan',
            'reviewer'
        ).filter(
            tugas__subproject__project__perusahaan=perusahaan_user
        )
    else:  # staff
        review_qs = Review.objects.select_related(
            'tugas',
            'tugas__subproject',
            'tugas__subproject__project',
            'tugas__subproject__project__perusahaan',
            'reviewer'
        ).filter(
            tugas__subproject__pegawai=user
        )
    review_qs = review_qs.order_by('-tgl_revisi', 'tugas__nama_file')

    # Hitung selisih waktu terlambat review
    review_dengan_selisih = []
    for review in review_qs:
        batas_jam = review.tugas.subproject.project.perusahaan.batas_waktu_review
        deadline_review = review.tugas.tgl_upload + timedelta(hours=batas_jam)
        tgl_review = review.tgl_revisi
        is_terlambat = tgl_review > deadline_review
        selisih = tgl_review - deadline_review if is_terlambat else deadline_review - tgl_review
        total_detik = int(selisih.total_seconds())
        hari = total_detik // 86400
        jam = (total_detik % 86400) // 3600
        menit = (total_detik % 3600) // 60

        if hari > 0:
            keterangan_waktu = f"{hari} hari {jam} jam {menit} menit"
        elif jam > 0:
            keterangan_waktu = f"{jam} jam {menit} menit"
        else:
            keterangan_waktu = f"{menit} menit"

        review_dengan_selisih.append({
            'review': review,
            'is_terlambat': is_terlambat,
            'keterangan_waktu': keterangan_waktu,
        })

    context = {
        'review_list': review_dengan_selisih,
        'tugas_list': Tugas.objects.all(),
        'pegawai_list': Pegawai.objects.all()
    }
    return render(request, 'review.html', context)

@login_required
def tambah_review(request):
    if request.method == 'POST':
        tugas_id = request.POST.get('tugas')
        catatan = request.POST.get('catatan')
        status = request.POST.get('status')
        Review.objects.create(
            tugas_id=tugas_id,
            catatan=catatan,
            status=status,
            reviewer=request.user,
            tgl_revisi=timezone.now()
        )
        return JsonResponse({
            'message': 'Review berhasil ditambahkan'
        }, status=200)
    return JsonResponse({
        'message': 'Request tidak valid'
    }, status=400)

@login_required
def edit_review(request):
    if request.method == 'POST':
        review_id = request.POST.get('id')
        review = Review.objects.get(id=review_id)
        review.catatan = request.POST.get('catatan')
        review.status = request.POST.get('status')
        review.save()
        return JsonResponse({
            'message':'Review berhasil diperbarui'
        })

@login_required
def hapus_review(request,id):
    if request.method == 'DELETE':
        review = Review.objects.get(id=id)
        review.delete()
        return JsonResponse({
            'message':'Review berhasil dihapus'
        })

@login_required
def kpi(request):
    import calendar as cal
    import json
    today = now().date()
    tahun_sekarang = today.year
    tahun_list = list(range(tahun_sekarang - 4, tahun_sekarang + 1))

    BULAN = [
        'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
        'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'
    ]

    if request.user.is_superuser:
        pegawai_list = Pegawai.objects.filter(is_superuser=False)
        project_qs = Project.objects.all()
        subproject_qs = Project.objects.none()
    elif request.user.role == 'manager':
        pegawai_list = Pegawai.objects.filter(
            perusahaan=request.user.perusahaan
        )
        project_qs = Project.objects.filter(
            perusahaan=request.user.perusahaan
        )
        subproject_qs = Project.objects.none()
    else:  # staff
        pegawai_list = Pegawai.objects.filter(
            perusahaan=request.user.perusahaan
        )
        project_qs = Project.objects.none()
        project_ids = Subproject.objects.filter(
            pegawai=request.user
        ).values_list('project_id', flat=True).distinct()
        subproject_qs = Project.objects.filter(id__in=project_ids)

    perusahaan_list = Perusahaan.objects.all()
    jabatan_list = Jabatan.objects.all()

    def build_grafik_data(qs, tahun_list, bulan_list):
        data_tahunan = []
        drilldown_series = []
        for tahun in tahun_list:
            count = qs.filter(
                mulai__lte=f"{tahun}-12-31",
                akhir__gte=f"{tahun}-01-01"
            ).count()
            data_tahunan.append({
                'name': str(tahun),
                'y': count,
                'drilldown': str(tahun)
            })
            data_bulanan = []
            for bulan_idx in range(1, 13):
                hari_terakhir = cal.monthrange(tahun, bulan_idx)[1]
                awal_bulan = f"{tahun}-{bulan_idx:02d}-01"
                akhir_bulan = f"{tahun}-{bulan_idx:02d}-{hari_terakhir}"
                count_bulan = qs.filter(
                    mulai__lte=akhir_bulan,
                    akhir__gte=awal_bulan
                ).count()
                data_bulanan.append([bulan_list[bulan_idx - 1], count_bulan])
            drilldown_series.append({
                'name': str(tahun),
                'id': str(tahun),
                'data': data_bulanan
            })
        return data_tahunan, drilldown_series

    # Grafik utama (semua / perusahaan user)
    data_tahunan, drilldown_series = build_grafik_data(
        project_qs, tahun_list, BULAN
    )

    # Grafik per perusahaan (hanya untuk superuser)
    grafik_per_perusahaan = {}
    if request.user.is_superuser:
        for p in perusahaan_list:
            qs_p = Project.objects.filter(perusahaan=p)
            dt, dd = build_grafik_data(qs_p, tahun_list, BULAN)
            grafik_per_perusahaan[str(p.id)] = {
                'tahunan': dt,
                'drilldown': dd
            }

    # Grafik staff
    data_tahunan_sub, drilldown_series_sub = build_grafik_data(
        subproject_qs, tahun_list, BULAN
    )

    context = {
        'pegawai_list': pegawai_list,
        'perusahaan_list': perusahaan_list,
        'jabatan_list': jabatan_list,
        'data_tahunan_json': json.dumps(data_tahunan),
        'drilldown_json': json.dumps(drilldown_series),
        'data_tahunan_sub_json': json.dumps(data_tahunan_sub),
        'drilldown_sub_json': json.dumps(drilldown_series_sub),
        'grafik_per_perusahaan_json': json.dumps(grafik_per_perusahaan),
    }
    return render(request, 'kpi.html', context)

@login_required
def get_kpi(request, pegawai_id):
    today = now().date()
    start = request.GET.get('start')
    end = request.GET.get('end')
    pegawai = Pegawai.objects.get(id=pegawai_id)

    tugas_filter = Tugas.objects.filter(subproject__pegawai=pegawai)
    project_filter = Project.objects.filter(dibuat_oleh=pegawai)
    review_filter = Review.objects.filter(
        reviewer=pegawai
    ).select_related('tugas__subproject')

    if start:
        start_date = make_aware(datetime.strptime(start, "%Y-%m-%d"))
        tugas_filter = tugas_filter.filter(tgl_upload__gte=start_date)
        project_filter = project_filter.filter(mulai__gte=start_date.date())
        review_filter = review_filter.filter(tgl_revisi__gte=start_date)

    if end:
        end_date = make_aware(datetime.strptime(end + " 23:59:59", "%Y-%m-%d %H:%M:%S"))
        tugas_filter = tugas_filter.filter(tgl_upload__lte=end_date)
        project_filter = project_filter.filter(mulai__lte=end_date.date())
        review_filter = review_filter.filter(tgl_revisi__lte=end_date)

    # KPI STAFF
    total_tugas = tugas_filter.count()
    tepat_waktu = tugas_filter.filter(terlambat="Tidak").count()
    terlambat = tugas_filter.filter(terlambat="Ya").count()

    # PERSENTASE SUBPROJECT TEPAT WAKTU PER PROJECT (untuk staff)
    subproject_per_project = {}
    tugas_qs = tugas_filter.select_related('subproject__project')
    for tugas in tugas_qs:
        project_nama = tugas.subproject.project.nama
        if project_nama not in subproject_per_project:
            subproject_per_project[project_nama] = {
                'tepat_waktu': 0,
                'total': 0
            }
        subproject_per_project[project_nama]['total'] += 1
        if tugas.terlambat == "Tidak":
            subproject_per_project[project_nama]['tepat_waktu'] += 1

    persentase_per_project = []
    for nama_project, data in subproject_per_project.items():
        total = data['total']
        tw = data['tepat_waktu']
        persen = round((tw / total) * 100, 1) if total > 0 else 0
        persentase_per_project.append({
            'project': nama_project,
            'tepat_waktu': tw,
            'total': total,
            'persen': persen
        })

    # KPI MANAGER
    total_project = project_filter.count()
    project_selesai = project_filter.filter(status='selesai').count()
    project_terlambat = project_filter.filter(
        status='ongoing',
        akhir__lt=today
    ).count()

    # KPI REVIEW MANAGER
    total_review = review_filter.count()
    review_tepat_waktu = 0
    review_terlambat = 0
    for review in review_filter.select_related(
        'tugas__subproject__project__perusahaan'
    ):
        # Skip jika relasi sudah NULL akibat akun terhapus
        if not review.tugas or not review.tugas.subproject:
            continue
        if not review.tugas.subproject.project:
            continue
        if not review.tugas.subproject.project.perusahaan:
            continue
        batas_jam = review.tugas.subproject.project.perusahaan.batas_waktu_review
        deadline_review = review.tugas.tgl_upload + timedelta(hours=batas_jam)
        if review.tgl_revisi > deadline_review:
            review_terlambat += 1
        else:
            review_tepat_waktu += 1

    persen_review_tepat_waktu = round(
        (review_tepat_waktu / total_review) * 100, 1
    ) if total_review > 0 else 0

    return JsonResponse({
        'nama': pegawai.nama,
        'role': pegawai.role,

        'total_tugas': total_tugas,
        'tepat_waktu': tepat_waktu,
        'terlambat': terlambat,
        'persentase_per_project': persentase_per_project,

        'total_project': total_project,
        'project_selesai': project_selesai,
        'project_terlambat': project_terlambat,

        'total_review': total_review,
        'review_tepat_waktu': review_tepat_waktu,
        'review_terlambat': review_terlambat,
        'persen_review_tepat_waktu': persen_review_tepat_waktu,
    })


@login_required
def cetak_kpi_pdf(request, pegawai_id):
    pegawai = Pegawai.objects.get(id=pegawai_id)
    today = now()
    start = request.GET.get('start')
    end = request.GET.get('end')

    tugas_filter = Tugas.objects.filter(subproject__pegawai=pegawai)
    project_filter = Project.objects.filter(dibuat_oleh=pegawai)
    review_filter = Review.objects.filter(
        reviewer=pegawai
    ).select_related('tugas__subproject')

    start_fmt = "-"
    end_fmt = "-"

    if start:
        start_date = make_aware(datetime.strptime(start, "%Y-%m-%d"))
        tugas_filter = tugas_filter.filter(tgl_upload__gte=start_date)
        project_filter = project_filter.filter(mulai__gte=start_date.date())
        review_filter = review_filter.filter(tgl_revisi__gte=start_date)
        start_fmt = format_tanggal_indo(start_date.date())

    if end:
        end_date = make_aware(datetime.strptime(end + " 23:59:59", "%Y-%m-%d %H:%M:%S"))
        tugas_filter = tugas_filter.filter(tgl_upload__lte=end_date)
        project_filter = project_filter.filter(mulai__lte=end_date.date())
        review_filter = review_filter.filter(tgl_revisi__lte=end_date)
        end_fmt = format_tanggal_indo(end_date.date())

    # KPI STAFF
    total_tugas = tugas_filter.count()
    tepat_waktu = tugas_filter.filter(terlambat="Tidak").count()
    terlambat = tugas_filter.filter(terlambat="Ya").count()

    subproject_per_project = {}
    tugas_qs = tugas_filter.select_related('subproject__project')
    for tugas in tugas_qs:
        project_nama = tugas.subproject.project.nama
        if project_nama not in subproject_per_project:
            subproject_per_project[project_nama] = {
                'tepat_waktu': 0,
                'total': 0
            }
        subproject_per_project[project_nama]['total'] += 1
        if tugas.terlambat == "Tidak":
            subproject_per_project[project_nama]['tepat_waktu'] += 1

    persentase_per_project = []
    for nama_project, data in subproject_per_project.items():
        total = data['total']
        tw = data['tepat_waktu']
        persen = round((tw / total) * 100, 1) if total > 0 else 0
        persentase_per_project.append({
            'project': nama_project,
            'tepat_waktu': tw,
            'total': total,
            'persen': persen
        })

    # KPI MANAGER
    total_project = project_filter.count()
    project_selesai = project_filter.filter(status='selesai').count()
    project_terlambat = project_filter.filter(
        status='ongoing',
        akhir__lt=today.date()
    ).count()

    # KPI REVIEW MANAGER
    total_review = review_filter.count()
    review_tepat_waktu = 0
    review_terlambat = 0
    for review in review_filter.select_related(
        'tugas__subproject__project__perusahaan'
    ):
        if not review.tugas or not review.tugas.subproject:
            continue
        if not review.tugas.subproject.project:
            continue
        if not review.tugas.subproject.project.perusahaan:
            continue
        batas_jam = review.tugas.subproject.project.perusahaan.batas_waktu_review
        deadline_review = review.tugas.tgl_upload + timedelta(hours=batas_jam)
        if review.tgl_revisi > deadline_review:
            review_terlambat += 1
        else:
            review_tepat_waktu += 1

    persen_review_tepat_waktu = round(
        (review_tepat_waktu / total_review) * 100, 1
    ) if total_review > 0 else 0

    template = get_template("kpi_pdf.html")
    waktu_lokal = timezone.localtime(timezone.now())
    context = {
        "perusahaan": pegawai.perusahaan.nama if pegawai.perusahaan else "-",
        "pegawai": pegawai,
        "start": start_fmt,
        "end": end_fmt,
        "tanggal_cetak": date_format(waktu_lokal, "d F Y, H:i") + " WIB",

        "total_tugas": total_tugas,
        "tepat_waktu": tepat_waktu,
        "terlambat": terlambat,

        "total_project": total_project,
        "project_selesai": project_selesai,
        "project_terlambat": project_terlambat,

        "total_review": total_review,
        "review_tepat_waktu": review_tepat_waktu,
        "review_terlambat": review_terlambat,

        "persentase_per_project": persentase_per_project,
        "persen_review_tepat_waktu": persen_review_tepat_waktu,
    }

    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="kpi.pdf"'
    pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=response)
    return response

@login_required
def grafik_pegawai(request, pegawai_id):
    import calendar as cal
    import json
    today = now().date()
    tahun_sekarang = today.year
    tahun_list = list(range(tahun_sekarang - 4, tahun_sekarang + 1))

    pegawai = get_object_or_404(Pegawai, id=pegawai_id)

    BULAN = [
        'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
        'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'
    ]

    # Project yang dikerjakan pegawai ini
    if pegawai.role == 'staff':
        project_ids = Subproject.objects.filter(
            pegawai=pegawai
        ).values_list('project_id', flat=True).distinct()
        project_qs = Project.objects.filter(id__in=project_ids)
    else:
        project_qs = Project.objects.filter(
            dibuat_oleh=pegawai
        )

    data_tahunan = []
    drilldown_series = []
    for tahun in tahun_list:
        count = project_qs.filter(
            mulai__lte=f"{tahun}-12-31",
            akhir__gte=f"{tahun}-01-01"
        ).count()
        data_tahunan.append({
            'name': str(tahun),
            'y': count,
            'drilldown': str(tahun)
        })
        data_bulanan = []
        for bulan_idx in range(1, 13):
            hari_terakhir = cal.monthrange(tahun, bulan_idx)[1]
            awal_bulan = f"{tahun}-{bulan_idx:02d}-01"
            akhir_bulan = f"{tahun}-{bulan_idx:02d}-{hari_terakhir}"
            count_bulan = project_qs.filter(
                mulai__lte=akhir_bulan,
                akhir__gte=awal_bulan
            ).count()
            data_bulanan.append([BULAN[bulan_idx - 1], count_bulan])
        drilldown_series.append({
            'name': str(tahun),
            'id': str(tahun),
            'data': data_bulanan
        })

    context = {
        'pegawai': pegawai,
        'data_tahunan_json': json.dumps(data_tahunan),
        'drilldown_json': json.dumps(drilldown_series),
    }
    return render(request, 'grafik_pegawai.html', context)

def format_tanggal_indo(tanggal):
    if not tanggal:
        return "-"
    bulan = [
        "Januari","Februari","Maret","April","Mei","Juni",
        "Juli","Agustus","September","Oktober","November","Desember"
    ]
    tgl = tanggal.day
    bln = bulan[tanggal.month - 1]
    thn = tanggal.year
    return f"{tgl} {bln} {thn}"


@login_required
def pegawai(request):
    user = request.user
    if user.is_superuser:
        pegawai_list = Pegawai.objects.filter(
            is_superuser=False
        ).order_by('username')
    elif user.role == "manager":
        pegawai_list = Pegawai.objects.filter(
            perusahaan=user.perusahaan,
            is_superuser=False
        ).order_by('username')
    else:
        return redirect('dashboard')
    perusahaan_list = Perusahaan.objects.all().order_by('nama')
    jabatan_list = Jabatan.objects.all().order_by('nama')
    context = {
        'pegawai_list': pegawai_list,
        'perusahaan_list': perusahaan_list,
        'jabatan_list': jabatan_list,
    }
    return render(request, 'pegawai.html', context)

@login_required
def tambah_pegawai(request):
    if request.method == "POST":
        username = request.POST.get('username')
        nama = request.POST.get('nama')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        perusahaan_id = request.POST.get('perusahaan')
        jabatan_id = request.POST.get('jabatan')
        role = request.POST.get('role')
        status_pegawai = request.POST.get('status_pegawai')
        status_akun = request.POST.get('status_akun')

        if password1 != password2:
            return JsonResponse({'message':'Password tidak cocok!'}, status=400)

        if Pegawai.objects.filter(username=username).exists():
            return JsonResponse({'message':'Username sudah digunakan!'}, status=400)

        perusahaan = Perusahaan.objects.get(id=perusahaan_id)
        jabatan = Jabatan.objects.get(id=jabatan_id)

        Pegawai.objects.create(
            username=username,
            nama=nama,
            email=email,
            password=make_password(password1),
            perusahaan=perusahaan,
            jabatan=jabatan,
            role=role,
            status_pegawai=status_pegawai,
            status_akun=status_akun,
            is_staff=True
        )
        return JsonResponse({'message':'Pegawai berhasil ditambahkan!'}, status=200)
    return JsonResponse({'message':'Invalid request'}, status=400)

@login_required
def edit_pegawai(request):
    if request.method == "POST":
        pegawai_id = request.POST.get('id')
        username = request.POST.get('username')
        nama = request.POST.get('nama')
        email = request.POST.get('email')
        perusahaan_id = request.POST.get('perusahaan')
        jabatan_id = request.POST.get('jabatan')
        role = request.POST.get('role')
        password = request.POST.get('password')
        status_pegawai = request.POST.get('status_pegawai')
        status_akun = request.POST.get('status_akun')
        pegawai = get_object_or_404(Pegawai, id=pegawai_id)

        if Pegawai.objects.filter(username=username).exclude(id=pegawai_id).exists():
            response_data = {
                'width':600,
                'title':'Username Tidak Tersedia',
                'text':'Username sudah digunakan.',
                'icon':'error'
            }
            return JsonResponse(response_data, status=400)

        pegawai.username = username
        pegawai.nama = nama
        pegawai.email = email
        pegawai.perusahaan_id = perusahaan_id
        pegawai.jabatan_id = jabatan_id
        pegawai.role = role
        pegawai.status_pegawai = status_pegawai
        pegawai.status_akun = status_akun

        if password:
            pegawai.set_password(password)
        pegawai.save()
        return JsonResponse({'message':'Pegawai berhasil diupdate'})
    return JsonResponse({'message':'Invalid request'}, status=400)

@login_required
def hapus_pegawai(request, id):
    if request.method == "DELETE":
        pegawai = get_object_or_404(Pegawai, id=id)
        pegawai.delete()
        return JsonResponse({'message':'Pegawai berhasil dihapus!'}, status=200)
    return JsonResponse({'error':'Invalid request method'}, status=400)

@login_required
def profile_view(request):
    return render(request, 'profile.html', {'user': request.user})
 
@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        new_username = request.POST.get('username')
 
        # Cek apakah username sudah digunakan pegawai lain
        if Pegawai.objects.filter(username=new_username).exclude(pk=user.pk).exists():
            return JsonResponse({
                'width': 480,
                'title': 'Username Tidak Tersedia',
                'text': 'Username sudah digunakan. Silakan pilih username lain.',
                'icon': 'error',
            }, status=400)
 
        user.nama = request.POST.get('nama')
        user.username = new_username
        user.email = request.POST.get('email')
 
        # Ganti password hanya jika diisi
        password = request.POST.get('password')
        if password:
            user.set_password(password)
            update_session_auth_hash(request, user)  # Jaga sesi tetap aktif setelah ganti password
 
        user.save()
 
        return JsonResponse({'redirect_url': reverse('profile_view')})
 
    return JsonResponse({'message': 'Invalid request'}, status=400)

@login_required
def logout_view(request):
    logout(request)
    return redirect('landing_page')