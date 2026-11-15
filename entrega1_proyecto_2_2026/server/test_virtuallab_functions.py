"""Pruebas unitarias de las funciones del servidor del laboratorio virtual.

Ejecucion desde la raiz del proyecto:
    python -m unittest discover -s server -p "test_*.py" -v

Cada prueba usa archivos temporales y no modifica los datos reales del proyecto.
"""
import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import virtuallab_functions as vf


def make_zip(contents=None):
    """Crea en memoria un ZIP valido para probar la carga de laboratorios."""
    contents = contents or {"demo.cir": "* test circuit\n.end\n", "nodes.txt": "in\nout\n"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
    return buffer.getvalue()


class ServerFunctionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(__file__)))
        root = self.temp.name
        self.users = os.path.join(root, "users.txt")
        self.sessions = os.path.join(root, "sessions.txt")
        self.labs_file = os.path.join(root, "labs.txt")
        self.assignments = os.path.join(root, "assignments.txt")
        self.labs_dir = os.path.join(root, "labs")
        self.paths_patch = patch.multiple(
            vf,
            usersFile=self.users,
            sessionsFile=self.sessions,
            labsFile=self.labs_file,
            assignmentsFile=self.assignments,
            labsDirectory=self.labs_dir,
        )
        self.paths_patch.start()
        self.addCleanup(self.paths_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def create_user(self, name, user_id, role, password):
        if not vf._read_records(self.users):
            if role == "professor":
                return vf.registerUser(name, user_id, role, password)
            vf.registerUser("Profe", "P1", "professor", "pw")
        professor_id = "P1"
        if vf._user(professor_id) is None:
            professor = next((x for x in vf._read_records(self.users)
                              if x.get("role") == "professor"), None)
            professor_id = professor.get("id") if professor else "P1"
        if not vf._logged_in(professor_id):
            vf.openSession(professor_id, "pw")
        return vf.registerUser(name, user_id, role, password, requester_id=professor_id)

    def login(self, user_id, password):
        return vf.openSession(user_id, password)

    def test_registers_student_and_normalizes_spanish_role(self):
        result = self.create_user(" Ana ", "S1", "estudiante", "clave")
        self.assertIn("registered", result)
        self.assertEqual(vf._user("S1")["role"], "student")
        self.assertEqual(vf._user("S1")["name"], "Ana")

    def test_rejects_incomplete_and_duplicate_registration(self):
        self.assertEqual(self.create_user("", "S1", "student", "pw"), "error")
        self.assertEqual(self.create_user("Ana", "S1", "unknown", "pw"), "error")
        self.create_user("Ana", "S1", "student", "pw")
        self.assertEqual(vf.registerUser("Otra", "S1", "student", "pw2", requester_id="P1"), "User already registered")
        self.assertEqual(vf.registerUser("Eva", "S2", "student", "pw2"), "error")

    def test_login_requires_correct_password_and_user_info_omits_password(self):
        self.create_user("Ana", "S1", "student", "clave")
        self.assertEqual(self.login("S1", "incorrecta"), "error")
        self.assertEqual(self.login("S1", "clave"), "Session was succesfully opened")
        profile = json.loads(vf.userInfo("S1"))
        self.assertEqual(profile, {"id": "S1", "name": "Ana", "role": "student"})
        self.assertNotIn("password", profile)

    def test_session_close_removes_access(self):
        self.create_user("Ana", "S1", "student", "clave")
        self.login("S1", "clave")
        self.assertEqual(vf.closeSession("S1"), "Session was succesfully closed")
        self.assertEqual(vf.userInfo("S1"), "error")
        self.assertEqual(vf.closeSession("S1"), "error")

    def test_only_logged_in_professor_can_upload_valid_zip(self):
        self.create_user("Profe", "P1", "professor", "pw")
        data = make_zip()
        self.assertEqual(vf.uploadLab("P1", "demo.zip", data), "error")
        self.login("P1", "pw")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", b"not a zip"), "error")
        self.assertEqual(vf.uploadLab("P1", "..\\escape.zip", data), "error")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", data), "File was succesfully received")
        self.assertTrue(os.path.isfile(os.path.join(self.labs_dir, "demo.zip")))

    def test_student_cannot_upload_and_professor_cannot_download(self):
        data = make_zip()
        self.create_user("Profe", "P1", "professor", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.login("P1", "pw")
        self.login("S1", "pw")
        self.assertEqual(vf.uploadLab("S1", "demo.zip", data), "error")
        vf.uploadLab("P1", "demo.zip", data)
        self.assertEqual(vf.downloadLab("P1", "demo.zip"), "error")

    def test_professor_lab_list_requires_professor_session(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.assertEqual(vf.listProfessorsLabs("P1"), "error")
        self.login("P1", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.login("S1", "pw")
        vf.uploadLab("P1", "demo.zip", make_zip())
        labs = json.loads(vf.listProfessorsLabs("P1"))
        self.assertEqual(labs[0]["file_name"], "demo.zip")
        self.assertEqual(vf.listProfessorsLabs("S1"), "error")

    def test_professor_lists_students_and_assigns_lab_student_can_download(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.create_user("Luis", "S2", "student", "pw")
        self.login("P1", "pw")
        self.login("S1", "pw")
        self.login("S2", "pw")
        data = make_zip()
        self.assertEqual(vf.uploadLab("P1", "demo.zip", data), "File was succesfully received")
        self.assertEqual(json.loads(vf.listStudents("P1")), [
            {"name": "Ana", "id": "S1"}, {"name": "Luis", "id": "S2"}
        ])
        self.assertEqual(vf.assignLab("P1", "demo", "S1"), "Lab was succesfully assigned")
        self.assertEqual(json.loads(vf.listStudentLabs("S1"))[0]["file_name"], "demo.zip")
        self.assertEqual(vf.downloadLab("S1", "demo.zip"), data)
        self.assertEqual(json.loads(vf.listStudentLabs("S2")), [])
        self.assertEqual(vf.downloadLab("S2", "demo.zip"), "error")

    def test_assignment_rejects_wrong_roles_and_unknown_labs(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.login("P1", "pw")
        self.assertEqual(vf.assignLab("P1", "missing", "S1"), "error")
        self.assertEqual(vf.assignLab("P1", "missing", "P1"), "error")
        self.assertEqual(vf.assignLab("S1", "missing", "S1"), "error")

    def test_assigning_same_lab_twice_does_not_duplicate_assignment(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.login("P1", "pw")
        self.login("S1", "pw")
        vf.uploadLab("P1", "demo.zip", make_zip())
        self.assertIn("succesfully assigned", vf.assignLab("P1", "demo", "S1"))
        self.assertIn("succesfully assigned", vf.assignLab("P1", "demo", "S1"))
        with open(self.assignments, encoding="utf-8") as file:
            self.assertEqual(len(file.readlines()), 1)



    def test_setup_status_changes_after_initial_professor_creation(self):
        self.assertTrue(json.loads(vf.setupStatus())["needs_initial_professor"])
        vf.registerUser("Profe", "P1", "professor", "pw")
        self.assertFalse(json.loads(vf.setupStatus())["needs_initial_professor"])

    def test_public_registration_and_professor_session_policy(self):
        self.assertIn("registered", vf.registerUser("Ana", "S1", "student", "pw"))
        self.assertIn("registered", vf.registerUser("Profe", "P1", "professor", "pw"))
        self.assertIn("registered", vf.registerUser("Otro", "P2", "professor", "pw"))
        vf.openSession("P1", "pw")
        self.login("S1", "pw")
        self.assertEqual(vf.registerUser("Luis", "S2", "student", "pw", requester_id="S1"), "error")

    def test_upload_requires_matching_netlist_and_valid_optional_svg(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.login("P1", "pw")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", make_zip({"other.cir": ".end"})), "error")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", make_zip({"demo.cir": ".end", "demo.svg": "<svg>"})), "error")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", make_zip({"demo.cir": ".end", "../escape.txt": "x"})), "error")
        self.assertEqual(vf.uploadLab("P1", "demo.zip", make_zip({"demo.cir": ".end", "demo.svg": "<svg xmlns='http://www.w3.org/2000/svg'/>"})), "File was succesfully received")

    def test_professor_cannot_assign_another_teachers_lab(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.login("P1", "pw")
        vf.uploadLab("P1", "demo.zip", make_zip())
        vf.closeSession("P1")
        self.create_user("Otra", "P2", "professor", "pw")
        self.login("P2", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.assertEqual(json.loads(vf.listProfessorsLabs("P2")), [])
        self.assertEqual(vf.assignLab("P2", "demo", "S1"), "error")


    def test_unregistered_or_logged_out_users_cannot_list_data(self):
        self.create_user("Profe", "P1", "professor", "pw")
        self.assertEqual(vf.listStudents("P1"), "error")
        self.assertEqual(vf.listStudentLabs("S1"), "error")
        self.login("P1", "pw")
        self.create_user("Ana", "S1", "student", "pw")
        self.assertEqual(vf.listStudentLabs("P1"), "error")
        self.assertEqual(vf.listStudents("S1"), "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)




