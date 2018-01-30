from towerkit import exceptions as exc
import pytest

from tests.api import Base_Api_Test


@pytest.mark.api
@pytest.mark.rbac
@pytest.mark.usefixtures('authtoken', 'install_enterprise_license_unlimited')
class TestJobsRBAC(Base_Api_Test):

    def test_v1_launch_as_superuser(self, job_template, api_jobs_pg):
        """Verify job creation via /api/v1/jobs/ and job start via /api/v2/jobs/N/start/."""
        job = api_jobs_pg.post(job_template.json)
        assert job.status == 'new'
        job.related.start.post()
        assert job.wait_until_completed().is_successful

    def test_v1_launch_as_non_superuser(self, job_template, non_superusers, api_jobs_pg):
        """Verify a non-superuser is unable to create a job via POST to the /api/v1/jobs/ endpoint."""
        for non_superuser in non_superusers:
            with self.current_user(non_superuser):
                with pytest.raises(exc.Forbidden):
                    api_jobs_pg.post(job_template.json)

    def test_v2_launch_as_all_users(self, factories, v2, all_users):
        """Creating jobs via post to /api/v2/jobs/ should raise 405."""
        for user in all_users:
            with self.current_user(user):
                with pytest.raises(exc.MethodNotAllowed):
                    v2.jobs.post()

    def test_relaunch_job_as_superuser(self, factories):
        jt = factories.v2_job_template()
        job = jt.launch().wait_until_completed()
        assert job.is_successful

        relaunched_job = job.relaunch().wait_until_completed()
        assert relaunched_job.is_successful

    def test_relaunch_job_as_organization_admin(self, factories):
        jt1, jt2 = [factories.v2_job_template() for _ in range(2)]
        user = factories.v2_user()
        jt1.ds.inventory.ds.organization.set_object_roles(user, 'admin')

        job1 = jt1.launch().wait_until_completed()
        job2 = jt2.launch().wait_until_completed()
        for job in [job1, job2]:
            assert job.is_successful

        with self.current_user(user):
            relaunched_job = job1.relaunch().wait_until_completed()
            assert relaunched_job.is_successful

            with pytest.raises(exc.Forbidden):
                job2.relaunch()

    def test_relaunch_as_organization_user(self, factories):
        jt = factories.v2_job_template()
        user = factories.v2_user()
        jt.ds.inventory.ds.organization.set_object_roles(user, 'member')

        job = jt.launch().wait_until_completed()
        assert job.is_successful

        with self.current_user(user):
            with pytest.raises(exc.Forbidden):
                job.relaunch()

    def test_relaunch_job_as_system_auditor(self, factories, job_with_status_completed):
        user = factories.user(is_system_auditor=True)
        with self.current_user(user):
            with pytest.raises(exc.Forbidden):
                job_with_status_completed.relaunch().wait_until_completed()
