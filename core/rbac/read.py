from typing import List, Dict
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

def list_all_users() -> List[Dict]:
    logger.info("list_all_users() called")
    client = get_weaviate_client()
    all_users = client.users.db.list_all()
    users_data = []
    for user in all_users:
        users_data.append({
            'User ID': user.user_id,
            'User Type': user.user_type.value,
            'Active': user.active,
            'Assigned Roles': ', '.join(user.role_names) if user.role_names else 'None'
        })
    return users_data

def list_all_roles() -> List[Dict]:
    logger.info("list_all_roles() called")
    client = get_weaviate_client()
    all_roles = client.roles.list_all()
    roles_data = []
    for role_name, role_obj in all_roles.items():
        total_permissions = 0
        permission_types = []
        if hasattr(role_obj, 'roles_permissions') and role_obj.roles_permissions:
            total_permissions += len(role_obj.roles_permissions)
            permission_types.append('Role Management')
        if hasattr(role_obj, 'users_permissions') and role_obj.users_permissions:
            total_permissions += len(role_obj.users_permissions)
            permission_types.append('User Management')
        if hasattr(role_obj, 'collections_permissions') and role_obj.collections_permissions:
            total_permissions += len(role_obj.collections_permissions)
            permission_types.append('Collections')
        if hasattr(role_obj, 'tenants_permissions') and role_obj.tenants_permissions:
            total_permissions += len(role_obj.tenants_permissions)
            permission_types.append('Tenants')
        if hasattr(role_obj, 'data_permissions') and role_obj.data_permissions:
            total_permissions += len(role_obj.data_permissions)
            permission_types.append('Data Objects')
        if hasattr(role_obj, 'backups_permissions') and role_obj.backups_permissions:
            total_permissions += len(role_obj.backups_permissions)
            permission_types.append('Backups')
        if hasattr(role_obj, 'cluster_permissions') and role_obj.cluster_permissions:
            total_permissions += len(role_obj.cluster_permissions)
            permission_types.append('Cluster')
        if hasattr(role_obj, 'nodes_permissions') and role_obj.nodes_permissions:
            total_permissions += len(role_obj.nodes_permissions)
            permission_types.append('Nodes')
        roles_data.append({
            'Role Name': role_name,
            'Permission Count': total_permissions,
            'Permission Types': ', '.join(permission_types) if permission_types else 'None'
        })
    return roles_data

def list_all_permissions() -> List[Dict]:
    logger.info("list_all_permissions() called")
    client = get_weaviate_client()
    all_roles = client.roles.list_all()
    permissions_data = []
    for role_name, role_obj in all_roles.items():
        # Role Management Permissions
        if hasattr(role_obj, 'roles_permissions') and role_obj.roles_permissions:
            for perm in role_obj.roles_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Role Management',
                    'Resource Filter': getattr(perm, 'role', '*'),
                    'Actions': ', '.join(actions),
                    'Scope': getattr(perm, 'scope', 'N/A')
                })
        # User Management Permissions
        if hasattr(role_obj, 'users_permissions') and role_obj.users_permissions:
            for perm in role_obj.users_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'User Management',
                    'Resource Filter': getattr(perm, 'user', '*'),
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Collections Permissions
        if hasattr(role_obj, 'collections_permissions') and role_obj.collections_permissions:
            for perm in role_obj.collections_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Collections',
                    'Resource Filter': getattr(perm, 'collection', '*'),
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Tenants Permissions
        if hasattr(role_obj, 'tenants_permissions') and role_obj.tenants_permissions:
            for perm in role_obj.tenants_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                resource_filter = f"Collection: {getattr(perm, 'collection', '*')}, Tenant: {getattr(perm, 'tenant', '*')}"
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Tenants',
                    'Resource Filter': resource_filter,
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Data Objects Permissions
        if hasattr(role_obj, 'data_permissions') and role_obj.data_permissions:
            for perm in role_obj.data_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                resource_filter = f"Collection: {getattr(perm, 'collection', '*')}, Tenant: {getattr(perm, 'tenant', '*')}"
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Data Objects',
                    'Resource Filter': resource_filter,
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Backups Permissions
        if hasattr(role_obj, 'backups_permissions') and role_obj.backups_permissions:
            for perm in role_obj.backups_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Backups',
                    'Resource Filter': getattr(perm, 'collection', '*'),
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Cluster Permissions
        if hasattr(role_obj, 'cluster_permissions') and role_obj.cluster_permissions:
            for perm in role_obj.cluster_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': 'Cluster',
                    'Resource Filter': 'N/A',
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
        # Nodes Permissions
        if hasattr(role_obj, 'nodes_permissions') and role_obj.nodes_permissions:
            for perm in role_obj.nodes_permissions:
                actions = [action.value for action in perm.actions] if hasattr(perm, 'actions') else []
                verbosity = getattr(perm, 'verbosity', 'unknown')
                collection_filter = getattr(perm, 'collection', '*') if verbosity == 'verbose' else 'All'
                permissions_data.append({
                    'Role Name': role_name,
                    'Permission Type': f'Nodes ({verbosity})',
                    'Resource Filter': collection_filter,
                    'Actions': ', '.join(actions),
                    'Scope': 'N/A'
                })
    return permissions_data

def list_users_roles_permissions_combined() -> List[Dict]:
    logger.info("list_users_roles_permissions_combined() called")
    client = get_weaviate_client()
    all_users = client.users.db.list_all()
    all_roles = client.roles.list_all()
    combined_data = []
    for user in all_users:
        if user.role_names:
            for role_name in user.role_names:
                if role_name in all_roles:
                    role_obj = all_roles[role_name]
                    permission_summary = []
                    if hasattr(role_obj, 'roles_permissions') and role_obj.roles_permissions:
                        permission_summary.append('Role Management')
                    if hasattr(role_obj, 'users_permissions') and role_obj.users_permissions:
                        permission_summary.append('User Management')
                    if hasattr(role_obj, 'collections_permissions') and role_obj.collections_permissions:
                        permission_summary.append('Collections')
                    if hasattr(role_obj, 'tenants_permissions') and role_obj.tenants_permissions:
                        permission_summary.append('Tenants')
                    if hasattr(role_obj, 'data_permissions') and role_obj.data_permissions:
                        permission_summary.append('Data Objects')
                    if hasattr(role_obj, 'backups_permissions') and role_obj.backups_permissions:
                        permission_summary.append('Backups')
                    if hasattr(role_obj, 'cluster_permissions') and role_obj.cluster_permissions:
                        permission_summary.append('Cluster')
                    if hasattr(role_obj, 'nodes_permissions') and role_obj.nodes_permissions:
                        permission_summary.append('Nodes')
                    combined_data.append({
                        'User ID': user.user_id,
                        'User Type': user.user_type.value,
                        'Role Name': role_name,
                        'Permission Areas': ', '.join(permission_summary) if permission_summary else 'None',
                        'Active': user.active
                    })
                else:
                    combined_data.append({
                        'User ID': user.user_id,
                        'User Type': user.user_type.value,
                        'Role Name': role_name,
                        'Active': user.active,
                        'Permission Areas': 'Role not found'
                    })
        else:
            combined_data.append({
                'User ID': user.user_id,
                'User Type': user.user_type.value,
                'Role Name': 'None',
                'Active': user.active,
                'Permission Areas': 'No permissions'
            })
    return combined_data
