import six

import fauxfactory
import pytest
from tests.api import Base_Api_Test

from common.exceptions import LicenseExceeded_Exception as Forbidden_Exception  # TODO: Fix this
import common.exceptions
from common.utils import random_utf8
from common.exceptions import NoContent_Exception
from common.exceptions import Method_Not_Allowed_Exception


pytestmark = [
    pytest.mark.nondestructive,
    pytest.mark.skip_selenium,
    pytest.mark.rbac,
    pytest.mark.usefixtures('authtoken', 'install_enterprise_license'),
]

# Tower 500's when navigating to projects/N/teams
TOWER_ISSUE_2114 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2114')
# 403 when navigating to projects/N/update as user with either project
# 'use' or project 'read'
TOWER_ISSUE_2124 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2124')
# User with credential 'owner' role can't edit and delete credentials
TOWER_ISSUE_2130 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2130')
# Users with any of our credential roles gets a 403 when navigating to
# credentials/N/users
TOWER_ISSUE_2129 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2129')
# User with inventory ad_hoc role can edit inventory
TOWER_ISSUE_2221 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2221')
# User with JT admin cannot edit JT
TOWER_ISSUE_2207 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2207')
# Inventory script admin cannot put/patch/delete inventory script
TOWER_ISSUE_2186 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2186')
# Cannot give a user the admin rights of another user
TOWER_ISSUE_2316 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2316')
# Tower should return NotFound for all endpoints for which
# a user does not have access
TOWER_ISSUE_2366 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2366')
# User with inventory update can put/patch inventory
TOWER_ISSUE_2409 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2409')
# We have improper nesting in our credential get_related
TOWER_ISSUE_2205 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2205')
# Project 'admin' and 'update' cannot launch project updates
TOWER_ISSUE_2489 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2489')
# 500-level error when navigating to credentials/N/owner_teams
TOWER_ISSUE_2543 = pytest.mark.github(
    'https://github.com/ansible/ansible-tower/issues/2543')


def tower_issue(issue_number, **kwargs):
    url = 'https://github.com/ansible/ansible-tower/issues/{0}'
    url = url.format(issue_number)
    return pytest.mark.github(url, **kwargs)


def check_role_association(user, model, role_name):
    __tracebackhide__ = True
    msg = 'Unable to verify {0} {1} role association'
    # check the related users endpoint of the role for user
    role = get_role(model, role_name)
    results = role.get_related('users').get(username=user.username)
    if results.count != 1:
        pytest.fail(msg.format(resource_name, role_name))


def check_role_disassociation(user, model, role_name):
    __tracebackhide__ = True
    msg = 'Unable to {0} {1} role disassociation'
    # check the related users endpoint of the role for absence of user
    role = get_role(model, role_name)
    results = role.get_related('users').get(username=user.username)
    if results.count != 0:
        pytest.fail(msg.format(resource_name, role_name))


def get_role(model, role_name):
    """Return a role page model for an api page model and role name.

    :param model: A resource api page model with related roles endpoint
    :role_name: The name of the role (case insensitive)

    Usage::
        >>> # get the description of the Use role for an inventory
        >>> bar_inventory = factories.inventory()
        >>> role_page = get_role_page(bar_inventory, 'Use')
        >>> role_page.description
        u'Can use the inventory in a job template'
    """
    search_name = role_name.lower()
    for role in model.object_roles:
        if role.name.lower() == search_name:
            return role
    msg = "Role '{0}' not found for {1}"
    msg = msg.format(role_name, type(model))
    raise ValueError(msg)


def set_roles(user, model, role_names, endpoint='related_users', disassociate=False):
    """Associate a list of roles to a user for a given api page model

    :param user: The api page model for a user
    :param model: A resource api page model with related roles endpoint
    :param role_names: A case insensitive list of role names
    :param endpoint: The endpoint to use when making the role association
    :param disassociate: A boolean flag indicating whether to associate or
        diassociate the role with the user

    Usage::
        >>> # Make a user that is an organization admin with 'Use' and
        >>> #'Update' roles on a test inventory
        >>> foo_organization = factories.organization(name='foo')
        >>> bar_inventory = factories.inventory(name='bar')
        >>> test_user = factories.user()
        >>> add_roles(test_user, foo_organization, ['admin'])
        >>> add_roles(test_user, bar_inventory, ['use', 'update'])
    """
    object_roles = [get_role(model, name) for name in role_names]
    for role in object_roles:
        if endpoint == 'related_users':
            payload = {'id': user.id}
            endpoint_model = role.get_related('users')
        elif endpoint == 'related_roles':
            payload = {'id': role.id}
            endpoint_model = user.get_related('roles')
        else:
            raise RuntimeError('Invalid role association endpoint')
        if disassociate:
            payload['disassociate'] = disassociate
        with pytest.raises(NoContent_Exception):
            endpoint_model.post(payload)

###############################################################################

@pytest.mark.parametrize(
    'endpoint',
    ['related_users', 'related_roles']
)
@pytest.mark.parametrize(
    'resource_name', 
    ['organization', 'project', 'inventory', 'credential', 'group', 'job_template']
)
def test_role_association_and_disassociation(factories, resource_name, endpoint):
    """Verify basic role association and disassociation functionality
    """
    user = factories.user()
    resource = getattr(factories, resource_name)()
    for role in resource.object_roles:
        role_name = role.name
        set_roles(user, resource, [role_name], endpoint=endpoint)
        check_role_association(user, resource, role_name)
        # disassociate the role from the user
        set_roles(user, resource, [role_name], endpoint=endpoint, disassociate=True)
        check_role_disassociation(user, resource, role_name)


@pytest.mark.parametrize(
    'endpoint',
    ['related_users', tower_issue('2226')('related_roles')]
)
@pytest.mark.parametrize(
    'resource_name,initial_role,unauthorized_target_role',
    [
        ('organization', 'member', 'admin'),
        ('project', 'read', 'admin'),
        ('inventory', 'read', 'admin'),
        ('job_template', 'read', 'admin'),
        ('group', 'read', 'admin'),
    ]
)
def test_unauthorized_self_privilege_escalation_returns_code_403(
        factories, auth_user, endpoint,
        resource_name, initial_role, unauthorized_target_role):
    """A user with [intial_role] permission on a [resource_name] cannot add
    the [unauthorized_target_role] for the [resource_name] to themselves
    """
    resource = getattr(factories, resource_name)()
    # make a test user and associate it with the initial role
    user = factories.user()
    set_roles(user, resource, [initial_role])
    with auth_user(user), pytest.raises(Forbidden_Exception):
        set_roles(user, resource, [unauthorized_target_role], endpoint=endpoint)


@tower_issue('2413', raises=Method_Not_Allowed_Exception)
@pytest.mark.parametrize('related_roles,access', [
    (
        {'credential': ['read'], 'inventory': ['use'], 'project': ['use']},
        {'get': True, 'relaunch': False}
    ),
    (
        {'credential': ['use'], 'inventory': ['read'], 'project': ['use']},
        {'get': True, 'relaunch': False}
    ),
    (
        {'credential': ['use'], 'inventory': ['use'], 'project': ['read']},
        {'get': True, 'relaunch': False}
    ),
    (
        {'credential': ['use'], 'inventory': ['use'], 'project': ['use']},
        {'get': True, 'relaunch': True}
    ),
])
def test_orphaned_job_read_and_relaunch_access(
        factories, auth_user, related_roles, access):
    """Verify expected orphaned job read and relaunch access for a set of
    related resource permissions
    """
    organization = factories.organization()
    user = factories.user(related_organization=organization)

    related_resources = {}
    for name, roles in related_roles.iteritems():
        resource = getattr(factories, name)(related_organization=organization)
        set_roles(user, resource, roles)
        related_resources['related_' + name] = resource

    job_template = factories.job_template(**related_resources)
    set_roles(user, organization, ['admin'])
    set_roles(user, job_template, ['admin'])

    orphan = job_template.launch()
    job_template.delete()

    for method_name, can_access in access.iteritems():
        if can_access:
            with auth_user(user):
                assert getattr(orphan, method_name)()
        else:
            with auth_user(user), pytest.raises(Forbidden_Exception):
                assert getattr(orphan, method_name)()


@pytest.mark.parametrize('initially_read_only', ['project', 'inventory', 'credential'])
def test_job_template_patch_request_without_usage_role_returns_code_403(
        factories, auth_user, initially_read_only):
    """Verify that a user cannot change the related project, inventory, or
    credential of a job template unless they have usage permissions on all
    three resources and are admins of the job template
    """
    organization = factories.organization()
    job_template = factories.job_template()
    # make user an org member and a job template admin
    user = factories.user()
    set_roles(user, organization, ['member'])
    set_roles(user, job_template, ['admin'])
    # populate patch dataset
    patch_resources = {}
    for resource_name in ('project', 'inventory', 'credential'):
        # generate test resource
        resource = getattr(factories, resource_name)()
        # assign role permissions to test user
        if resource_name == initially_read_only:
            # In each parametrized version of this test, one of the resources
            # in the patch request payload is made read-only for the test user
            set_roles(user, resource, ['read'])
        else:
            set_roles(user, resource, ['use'])
        # add resource to patch dataset
        patch_resources[resource_name] = resource
    # verify that attempts to patch the job template without usage
    # permission are forbidden
    patch_payload = {key: obj.id for key, obj in patch_resources.items()}
    with auth_user(user), pytest.raises(Forbidden_Exception):
        job_template.patch(**patch_payload)
    # add usage permissions to the restricted resource
    set_roles(user, patch_resources[initially_read_only], ['use'])
    # verify that the patch request is now permitted
    with auth_user(user):
        assert job_template.patch(**patch_payload)


def test_job_template_creators_are_added_to_admin_role(
        factories, auth_user, api_job_templates_pg):
    """Verify that job template creators are added to the admin role of the 
    created job template
    """
    credential = factories.credential()
    project = factories.project()
    inventory = factories.inventory()
    # set user resource role associations
    user = factories.user()
    set_roles(user, credential, ['use'])
    set_roles(user, project, ['use'])
    set_roles(user, inventory, ['use'])
    # create a job template as the test user
    with auth_user(user):
        job_template = api_job_templates_pg.post({
            'name': fauxfactory.gen_alphanumeric(),
            'description': fauxfactory.gen_utf8(),
            'job_type': 'run',
            'playbook': 'site.yml',
            'project': project.id,
            'inventory': inventory.id,
            'credential': credential.id,
        })
    # verify succesful job_template admin role association
    check_role_association(user, job_template, 'admin')


def test_job_template_post_request_without_network_credential_access_returns_code_403(
        factories, auth_user, api_job_templates_pg):
    """Verify that job_template post requests with network credentials in
    the payload are only permitted if the user making the request has usage 
    permission for the network credential.
    """
    project = factories.project()
    inventory = factories.inventory()
    credential = factories.credential(kind='ssh')
    network_credential = factories.credential(kind='net')
    # set user resource role associations
    user = factories.user()
    set_roles(user, credential, ['use'])
    set_roles(user, project, ['use'])
    set_roles(user, inventory, ['use'])
    set_roles(user, network_credential, ['read'])
    # create a job template post request payload
    payload = {
        'name': fauxfactory.gen_alphanumeric(),
        'description': fauxfactory.gen_utf8(),
        'job_type': 'run',
        'playbook': 'site.yml',
        'project': project.id,
        'inventory': inventory.id,
        'credential': credential.id,
        'network_credential': network_credential.id, 
    }
    with auth_user(user), pytest.raises(Forbidden_Exception):
        api_job_templates_pg.post(payload)
    # add network credential access to test user
    set_roles(user, network_credential, ['use'])
    # verify that the post request is now permitted
    with auth_user(user):
        assert api_job_templates_pg.post(payload)


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Organization_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, user_password):
        '''
        An unprivileged user should not be able to:
        * Issue GETs to our organization details page
        * Issue GETs to all of this organization's related pages
        * Edit our organization
        * Delete our organization
        '''
        organization_pg = factories.organization()
        user_pg = factories.user()

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                organization_pg.get()
            for related in organization_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    organization_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                organization_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                organization_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                organization_pg.delete()

    def test_auditor_role(self, factories, user_password):
        '''
        An organization auditor should be able to do the following:
        * Issue GETs to our organization details page
        * Issue GETs to all of this organization's related pages

        An organization auditor should not be able to do the following:
        * Edit our organization
        * Delete our organization
        '''
        organization_pg = factories.organization()
        user_pg = factories.user()

        # give test user auditor privileges
        role_pg = organization_pg.get_object_role('auditor_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            organization_pg.get()
            for related in organization_pg.json.related:
                organization_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.delete()

    def test_admin_role(self, factories, user_password):
        '''
        An organization admin should be able to do the following:
        * GET our organization details page
        * GET all of our organization's related pages
        * Edit our organization
        * Delete our organization
        '''
        organization_pg = factories.organization()
        user_pg = factories.user()

        # give test user admin privileges
        role_pg = organization_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            organization_pg.get()
            for related in organization_pg.json.related:
                organization_pg.get_related(related)

            # check put/patch/delete
            organization_pg.put()
            organization_pg.patch()
            organization_pg.delete()

    def test_member_role(self, factories, user_password):
        '''
        Tests that a user with 'member_role' has the following:
        * The ability to make a GET to our target organization
        * The ability to make a GET against our organization's related endpoints

        Our user, however, should not be able to:
        * Edit our organization
        * Delete our organization
        '''
        organization_pg = factories.organization()
        user_pg = factories.user()

        # give test user member privileges
        role_pg = organization_pg.get_object_role('member_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            organization_pg.get()
            for related in organization_pg.json.related:
                organization_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.delete()

    def test_read_role(self, factories, user_password):
        '''
        Tests that a user with 'read_role' has the following:
        * The ability to make a GET to our target organization
        * The ability to make a GET against our organization's related endpoints

        Our user, however, should not be able to:
        * Edit our organization
        * Delete our organization
        '''
        organization_pg = factories.organization()
        user_pg = factories.user()

        # give test user read role privileges
        role_pg = organization_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            organization_pg.get()
            for related in organization_pg.json.related:
                organization_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                organization_pg.delete()

    def test_member_role_association(self, factories, user_password):
        '''
        Tests that after a user is granted member_role that he now shows
        up under organizations/N/users.
        '''
        user_pg = factories.user()
        organization_pg = factories.organization()

        # organization by default should have no users
        users_pg = organization_pg.get_related('users')
        assert users_pg.count == 0, "%s user[s] unexpectedly found for organization/%s." % (users_pg.count, organization_pg.id)

        # give test user member role privileges
        role_pg = organization_pg.get_object_role('member_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # assert that organizations/N/users now shows test user
        assert users_pg.get().count == 1, "Expected one user for organization/%s/users/, got %s." % (organization_pg.id, users_pg.count)
        assert users_pg.results[0].id == user_pg.id, \
            "Organization user not our target user. Expected user with ID %s but got one with ID %s." % (user_pg.id, users_pg.results[0].id)

    def test_autopopulated_member_role(self, organization, org_user, user_password):
        '''
        Tests that when you create a user by posting to organizations/N/users
        that the user is automatically created with a member_role for this
        organization.
        '''
        # assert test user created in target organization
        organizations_pg = org_user.get_related('organizations')
        assert organizations_pg.count == 1, \
            "Unexpected number of organizations returned. Expected 1, got %s." % organizations_pg.count
        assert organizations_pg.results[0].id == organization.id, \
            "org_user not created in organization/%s." % organization.id

        # assert test user created with member_role
        roles_pg = org_user.get_related('roles')
        assert roles_pg.count == 1, \
            "Unexpected number of roles returned. Expected 1, got %s." % roles_pg.count
        role_pg = roles_pg.results[0]
        assert role_pg.id == organization.get_object_role('member_role').id, \
            "Unexpected user role returned. Expected %s, got %s." % (organization.get_object_role('member_role').id, role_pg.id)


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Project_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, user_password):
        '''
        An unprivileged user should not be able to:
        * GET our project detail page
        * GET all project related pages
        * Launch project updates
        * Use our project in a JT
        * Edit our project
        * Delete our project

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        project_pg = factories.project()
        user_pg = factories.user()
        update_pg = project_pg.get_related('update')

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                project_pg.get()
            for related in project_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    project_pg.get_related(related)

            # check project update
            with pytest.raises(common.exceptions.NotFound_Exception):
                update_pg.post()

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                project_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                project_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                project_pg.delete()

    def test_admin_role(self, factories, user_password):
        '''
        A project admin should be able to:
        * GET our project detail page
        * GET all project related pages
        * Launch project updates
        * Use our project in a JT
        * Edit our project
        * Delete our project

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        project_pg = factories.project()
        user_pg = factories.user()

        # give user admin_role
        role_pg = project_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            project_pg.get()
            for related in project_pg.json.related:
                # 403 when navigating to projects/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        project_pg.get_related(related)
                else:
                    project_pg.get_related(related)

            # check project update
            project_pg.update()

            # check put/patch/delete
            project_pg.put()
            project_pg.patch()
            project_pg.delete()

    def test_update_role(self, factories, user_password):
        '''
        A user with project update should be able to:
        * GET our project detail page
        * GET all project related pages
        * Launch project updates

        A user with project update should not be able to:
        * Use our project in a JT
        * Edit our project
        * Delete our project

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        project_pg = factories.project()
        user_pg = factories.user()

        # give user update_role
        role_pg = project_pg.get_object_role('update_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            project_pg.get()
            for related in project_pg.json.related:
                # 403 when navigating to projects/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        project_pg.get_related(related)
                else:
                    project_pg.get_related(related)

            # check project update
            project_pg.update()

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.delete()

    def test_use_role(self, factories, user_password):
        '''
        A user with project update should be able to:
        * GET our project detail page
        * GET all project related pages
        * Use our project in a JT

        A user with project update should not be able to:
        * Launch project updates
        * Edit our project
        * Delete our project

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        project_pg = factories.project()
        user_pg = factories.user()

        # give user use_role
        role_pg = project_pg.get_object_role('use_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            project_pg.get()
            for related in project_pg.json.related:
                # 403 when navigating to projects/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        project_pg.get_related(related)
                else:
                    project_pg.get_related(related)

            # check project update
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.update()

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.delete()

    def test_read_role(self, factories, user_password):
        '''
        A user with project read should be able to:
        * GET our project detail page
        * GET all project related pages

        A user with project read should not be able to:
        * Launch project updates
        * Use our project in a JT
        * Edit our project
        * Delete our project

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        project_pg = factories.project()
        user_pg = factories.user()

        # give user read_role
        role_pg = project_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            project_pg.get()
            for related in project_pg.json.related:
                # 403 when navigating to projects/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        project_pg.get_related(related)
                else:
                    project_pg.get_related(related)

            # check project update
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.update()

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                project_pg.delete()


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Credential_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, user_password):
        '''
        An unprivileged user should not be able to:
        * Make GETs to the credential detail page
        * Make GETs to all of the credential get_related
        # Use this credential in creating a JT
        * Edit the credential
        * Delete the credential

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        credential_pg = factories.credential()
        user_pg = factories.user()

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                credential_pg.get()
            for related in credential_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    credential_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                credential_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                credential_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                credential_pg.delete()

    def test_admin_role(self, factories, user_password):
        '''
        A user with credential 'owner' should be able to:
        * Make GETs to the credential detail page
        * Make GETs to all of the credential get_related
        # Use this credential in creating a JT
        * Edit the credential
        * Delete the credential

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            credential_pg.get()
            for related in credential_pg.json.related:
                credential_pg.get_related(related)

            # check put/patch/delete
            credential_pg.put()
            credential_pg.patch()
            credential_pg.delete()

    def test_use_role(self, factories, user_password):
        '''
        A user with credential 'use' should be able to:
        * Make GETs to the credential detail page
        * Make GETs to all of the credential get_related
        * Use this credential in creating a JT

        A user with credential 'use' should not be able to:
        * Edit the credential
        * Delete the credential

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user use_role
        role_pg = credential_pg.get_object_role('use_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            credential_pg.get()
            for related in credential_pg.json.related:
                credential_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.delete()

    def test_read_role(self, factories, user_password):
        '''
        A user with credential 'read' should be able to:
        * Make GETs to the credential detail page
        * Make GETs to all of the credential get_related

        A user with credential 'read' should not be able to:
        * Use this credential in creating a JT
        * Edit the credential
        * Delete the credential

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user read_role
        role_pg = credential_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            credential_pg.get()
            for related in credential_pg.json.related:
                credential_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                credential_pg.delete()


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Team_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, user_password):
        '''
        An unprivileged user may not be able to:
        * Get the team details page
        * Get all of the team related pages
        * Edit the team
        * Delete the team
        '''
        team_pg = factories.team()
        user_pg = factories.user()

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                team_pg.get()
            for related in team_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    team_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                team_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                team_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                team_pg.delete()

    def test_admin_role(self, factories, user_password):
        '''
        A user with team 'admin_role' should be able to:
        * Get the team details page
        * Get all of the team related pages
        * Edit the team
        * Delete the team
        '''
        team_pg = factories.team()
        user_pg = factories.user()

        # give user admin_role
        role_pg = team_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            team_pg.get()
            for related in team_pg.json.related:
                # 403 when navigating to teams/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        team_pg.get_related(related)
                else:
                    team_pg.get_related(related)

            # check put/patch/delete
            team_pg.put()
            team_pg.patch()
            team_pg.delete()

    def test_member_role(self, factories, user_password):
        '''
        A user with team 'member_role' should be able to:
        * Get the team details page
        * Get all of the team related pages

        A user with team 'member_role' should not be able to:
        * Edit the team
        * Delete the team
        '''
        team_pg = factories.team()
        user_pg = factories.user()

        # give user member_role
        role_pg = team_pg.get_object_role('member_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            team_pg.get()
            for related in team_pg.json.related:
                # 403 when navigating to teams/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        team_pg.get_related(related)
                else:
                    team_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.delete()

    def test_read_role(self, factories, user_password):
        '''
        A user with team 'read_role' should be able to:
        * Get the team details page
        * Get all of the team related pages

        A user with team 'read_role' should not be able to:
        * Edit the team
        * Delete the team
        '''
        team_pg = factories.team()
        user_pg = factories.user()

        # give user read_role
        role_pg = team_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            team_pg.get()
            for related in team_pg.json.related:
                # 403 when navigating to teams/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        team_pg.get_related(related)
                else:
                    team_pg.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                team_pg.delete()

    def test_member_role_association(self, factories, user_password):
        '''
        Tests that after a user is granted member_role that he now shows
        up under teams/N/users.
        '''
        team_pg = factories.team()
        user_pg = factories.user()

        # team by default should have no users
        users_pg = team_pg.get_related('users')
        assert users_pg.count == 0, "%s user[s] unexpectedly found for teams/%s." % (users_pg.count, team_pg.id)

        # give test user member role privileges
        role_pg = team_pg.get_object_role('member_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # assert that teams/N/users now shows test user
        assert users_pg.get().count == 1, "Expected one user for teams/%s/users/, got %s." % (team_pg.id, users_pg.count)
        assert users_pg.results[0].id == user_pg.id, \
            "Team user not our target user. Expected user with ID %s but got one with ID %s." % (user_pg.id, users_pg.results[0].id)


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Inventory_Script_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, inventory_script, user_password):
        '''
        An unprivileged user may not be able to:
        * Get your inventory_script detail page
        * Get all of your inventory_script get_related
        * Edit your inventory script
        * Delete your inventory script
        '''
        user_pg = factories.user()

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_script.get()
            for related in inventory_script.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    inventory_script.get_related(related)

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_script.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_script.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_script.delete()

    def test_admin_role(self, factories, inventory_script, user_password):
        '''
        A user with inventory_script 'admin' should be able to:
        * Get your inventory_script detail page
        * Get all of your inventory_script get_related
        * Edit your inventory script
        * Delete your inventory script
        '''
        user_pg = factories.user()

        # assert value for 'script' present
        assert inventory_script.script
        script = inventory_script.script

        # give user admin_role
        role_pg = inventory_script.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_script.get()
            for related in inventory_script.json.related:
                # 403 when navigating to inventory_scripts/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_script.get_related(related)
                else:
                    inventory_script.get_related(related)

            # check that value of 'script' viewable
            assert inventory_script.script == script, \
                "Unexpected value for 'script'; expected %s but got %s." % (script, inventory_script.script)

            # check put/patch/delete
            inventory_script.put()
            inventory_script.patch()
            inventory_script.delete()

    def test_read_role(self, factories, inventory_script, user_password):
        '''
        A user with inventory_script 'read' should be able to:
        * Get your inventory_script detail page
        * Get all of your inventory_script get_related

        A user with inventory_script 'read' should not be able to:
        * Edit your inventory script
        * Delete your inventory script
        '''
        user_pg = factories.user()

        # assert value for 'script' present
        assert inventory_script.script

        # give user read_role
        role_pg = inventory_script.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_script.get()
            for related in inventory_script.json.related:
                # 403 when navigating to inventory_scripts/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_script.get_related(related)
                else:
                    inventory_script.get_related(related)

            # check that value of 'script' not viewable
            assert not inventory_script.script, \
                "Unexpected value for 'script'; expected null but got %s." % inventory_script.script

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_script.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_script.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_script.delete()


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Job_Template_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, factories, user_password):
        '''
        An unprivileged_user should not be able to:
        * Get the JT details page
        * Get all of the JT get_related pages
        * Launch the JT
        * Edit the JT
        * Delete the JT
        '''
        job_template_pg = factories.job_template()
        user_pg = factories.user()
        launch_pg = job_template_pg.get_related('launch')

        with self.current_user(username=user_pg.username, password=user_password):
            with pytest.raises(common.exceptions.NotFound_Exception):
                job_template_pg.get()
            for related in job_template_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    job_template_pg.get_related(related)

            # check JT launch
            with pytest.raises(common.exceptions.NotFound_Exception):
                launch_pg.post()

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                job_template_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                job_template_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                job_template_pg.delete()

    def test_admin_role(self, factories, user_password):
        '''
        A user with JT admin should be able to:
        * Get the JT details page
        * Get all of the JT get_related pages
        * Launch the JT
        * Edit the JT
        * Delete the JT
        '''
        job_template_pg = factories.job_template()
        user_pg = factories.user()

        # give user admin_role
        role_pg = job_template_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            job_template_pg.get()
            for related in job_template_pg.json.related:
                # 403 when navigating to the following related is expected
                if related in ['credential', 'inventory', 'project']:
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        job_template_pg.get_related(related)
                else:
                    job_template_pg.get_related(related)

            # check JT launch
            job_pg = job_template_pg.launch().wait_until_completed()
            assert job_pg.is_successful, "Job unsuccessful - %s." % job_pg

            # check put/patch/delete
            job_template_pg.put()
            job_template_pg.patch()
            job_template_pg.delete()

    def test_execute_role(self, factories, user_password):
        '''
        A user with JT execute should be able to:
        * Get the JT details page
        * Get all of the JT get_related pages
        * Launch the JT

        And should not be able to:
        * Edit the JT
        * Delete the JT
        '''
        job_template_pg = factories.job_template()
        user_pg = factories.user()

        # give user execute_role
        role_pg = job_template_pg.get_object_role('execute_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            job_template_pg.get()
            for related in job_template_pg.json.related:
                # 403 when navigating to the following related is expected
                if related in ['credential', 'inventory', 'project']:
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        job_template_pg.get_related(related)
                else:
                    job_template_pg.get_related(related)

            # check JT launch
            job_pg = job_template_pg.launch().wait_until_completed()
            assert job_pg.is_successful, "Job unsuccessful - %s." % job_pg

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.delete()

    def test_read_role(self, factories, user_password):
        '''
        A user with JT admin should be able to:
        * Get the JT details page
        * Get all of the JT get_related pages

        And should not be able to:
        * Launch the JT
        * Edit the JT
        * Delete the JT
        '''
        job_template_pg = factories.job_template()
        user_pg = factories.user()

        # give user admin_role
        role_pg = job_template_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            job_template_pg.get()
            for related in job_template_pg.json.related:
                # 403 when navigating to the following related is expected
                if related in ['credential', 'inventory', 'project']:
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        job_template_pg.get_related(related)
                else:
                    job_template_pg.get_related(related)

            # check JT launch
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.launch()

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                job_template_pg.delete()


@pytest.mark.api
@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Inventory_RBAC(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_license_unlimited')

    @TOWER_ISSUE_2366
    def test_unprivileged_user(self, host_local, cloud_groups, custom_group, user_password, factories):
        '''
        An unprivileged user should not be able to:
        * Get the inventory detail
        * Get all of the inventory get_related
        * Update all groups that the inventory contains
        * Launch ad hoc commands against the inventory
        * Use the inventory in creating a JT
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        user_pg = factories.user()

        command_pg = inventory_pg.get_related('ad_hoc_commands')
        inventory_source_pgs = [cloud_group.get_related('inventory_source') for cloud_group in cloud_groups]
        inventory_source_update_pgs = [inventory_source_pg.get_related('update') for inventory_source_pg in inventory_source_pgs]
        custom_group_update_pg = custom_group.get_related('inventory_source')

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_pg.get()
            for related in inventory_pg.json.related:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    inventory_pg.get_related(related)

            # update all cloud_groups
            for inventory_source_update_pg in inventory_source_update_pgs:
                with pytest.raises(common.exceptions.NotFound_Exception):
                    inventory_source_update_pg.post()

            # update custom group
            with pytest.raises(common.exceptions.NotFound_Exception):
                custom_group_update_pg.post()

            # post command
            with pytest.raises(common.exceptions.NotFound_Exception):
                command_pg.post()

            # check put/patch/delete
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_pg.put()
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_pg.patch()
            with pytest.raises(common.exceptions.NotFound_Exception):
                inventory_pg.delete()

    def test_admin_role(self, host_local, cloud_groups, custom_group, user_password, factories):
        '''
        A user with inventory admin should be able to:
        * Get the inventory detail
        * Get all of the inventory get_related
        * Update all groups that the inventory contains
        * Launch ad hoc commands against the inventory
        * Use the inventory in creating a JT
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user inventory admin_role
        role_pg = inventory_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # give user credential admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_pg.get()
            for related in inventory_pg.json.related:
                # 403 when navigating to inventories/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_pg.get_related(related)
                else:
                    inventory_pg.get_related(related)

            # update all cloud_groups
            for cloud_group in cloud_groups:
                update_pg = custom_group.get_related('inventory_source').get_related('update')
                update_pg.post()

            # update custom group
            update_pg = custom_group.get_related('inventory_source').get_related('update')
            update_pg.post()

            # post command
            payload = dict(inventory=inventory_pg.id,
                           credential=credential_pg.id,
                           module_name="ping",
                           limit=host_local.name, )
            command_pg = inventory_pg.get_related('ad_hoc_commands').post(payload).wait_until_completed()
            assert command_pg.is_successful, "Command unsuccessful - %s." % command_pg

            # check put/patch/delete
            inventory_pg.put()
            inventory_pg.patch()
            inventory_pg.delete()

    def test_use_role(self, host_local, custom_group, user_password, factories):
        '''
        A user with inventory use should be able to:
        * Get the inventory detail
        * Get all of the inventory get_related
        * Use the inventory in creating a JT

        A user with inventory use should not be able to:
        * Update all groups that the inventory contains
        * Launch ad hoc commands against the inventory
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user inventory use_role
        role_pg = inventory_pg.get_object_role('use_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # give user credential admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_pg.get()
            for related in inventory_pg.json.related:
                # 403 when navigating to inventories/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_pg.get_related(related)
                else:
                    inventory_pg.get_related(related)

            # update custom group
            update_pg = custom_group.get_related('inventory_source').get_related('update')
            with pytest.raises(common.exceptions.Forbidden_Exception):
                update_pg.post()

            # post command
            payload = dict(inventory=inventory_pg.id,
                           credential=credential_pg.id,
                           module_name="ping",
                           limit=host_local.name, )
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.get_related('ad_hoc_commands').post(payload)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.delete()

    def test_adhoc_role(self, host_local, custom_group, user_password, factories):
        '''
        A user with inventory adhoc should be able to:
        * Get the inventory detail
        * Get all of the inventory get_related
        * Launch ad hoc commands against the inventory

        A user with inventory adhoc should not be able to:
        * Update all groups that the inventory contains
        * Use the inventory in creating a JT
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user inventory adhoc
        role_pg = inventory_pg.get_object_role('adhoc_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # give user credential admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_pg.get()
            for related in inventory_pg.json.related:
                # 403 when navigating to inventories/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_pg.get_related(related)
                else:
                    inventory_pg.get_related(related)

            # update custom group
            update_pg = custom_group.get_related('inventory_source').get_related('update')
            with pytest.raises(common.exceptions.Forbidden_Exception):
                update_pg.post()

            # post command
            payload = dict(inventory=inventory_pg.id,
                           credential=credential_pg.id,
                           module_name="ping",
                           limit=host_local.name, )
            command_pg = inventory_pg.get_related('ad_hoc_commands').post(payload).wait_until_completed()
            assert command_pg.is_successful, "Command unsuccessful - %s." % command_pg

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.delete()

    def test_update_role(self, host_local, cloud_groups, custom_group, user_password, factories):
        '''
        A user with inventory update should be able to:
        * Get the inventory detail
        * Get all of the inventory get_related
        * Update all groups that the inventory contains

        A user with inventory update should not be able to:
        * Launch ad hoc commands against the inventory
        * Use the inventory in creating a JT
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user inventory update_role
        role_pg = inventory_pg.get_object_role('update_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # give user credential admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_pg.get()
            for related in inventory_pg.json.related:
                # 403 when navigating to inventories/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_pg.get_related(related)
                else:
                    inventory_pg.get_related(related)

            # update all cloud_groups
            for cloud_group in cloud_groups:
                update_pg = custom_group.get_related('inventory_source').get_related('update')
                update_pg.post()

            # update custom group
            update_pg = custom_group.get_related('inventory_source').get_related('update')
            update_pg.post()

            # post command
            payload = dict(inventory=inventory_pg.id,
                           credential=credential_pg.id,
                           module_name="ping",
                           limit=host_local.name, )
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.get_related('ad_hoc_commands').post(payload)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.delete()

    def test_read_role(self, host_local, custom_group, user_password, factories):
        '''
        A user with inventory read should be able to:
        * Get the inventory detail
        * Get all of the inventory get_related

        A user with inventory read should not be able to:
        * Update all groups that the inventory contains
        * Launch ad hoc commands against the inventory
        * Use the inventory in creating a JT
        * Edit the inventory
        * Delete the inventory

        Use tested already in test_usage_role_required_to_change_other_job_template_related_resources.
        '''
        inventory_pg = host_local.get_related('inventory')
        credential_pg = factories.credential()
        user_pg = factories.user()

        # give user inventory read_role
        role_pg = inventory_pg.get_object_role('read_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        # give user credential admin_role
        role_pg = credential_pg.get_object_role('admin_role')
        with pytest.raises(common.exceptions.NoContent_Exception):
            user_pg.get_related('roles').post(dict(id=role_pg.id))

        with self.current_user(username=user_pg.username, password=user_password):
            # check GET as test user
            inventory_pg.get()
            for related in inventory_pg.json.related:
                # 403 when navigating to inventories/N/organization is expected
                if related == 'organization':
                    with pytest.raises(common.exceptions.Forbidden_Exception):
                        inventory_pg.get_related(related)
                else:
                    inventory_pg.get_related(related)

            # update custom group
            update_pg = custom_group.get_related('inventory_source').get_related('update')
            with pytest.raises(common.exceptions.Forbidden_Exception):
                update_pg.post()

            # post command
            payload = dict(inventory=inventory_pg.id,
                           credential=credential_pg.id,
                           module_name="ping",
                           limit=host_local.name, )
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.get_related('ad_hoc_commands').post(payload)

            # check put/patch/delete
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.put()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.patch()
            with pytest.raises(common.exceptions.Forbidden_Exception):
                inventory_pg.delete()

