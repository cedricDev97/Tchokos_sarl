from django.contrib.auth.models import Group

def has_group(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()

def is_super_admin(user) -> bool:
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or has_group(user, "super_admin")
    )

def can_manage_orders(user) -> bool:
    return is_super_admin(user) or has_group(user, "admin_orders")

def can_manage_payments(user) -> bool:
    return is_super_admin(user) or has_group(user, "admin_payments")

def can_manage_inventory(user) -> bool:
    return is_super_admin(user) or has_group(user, "admin_inventory")

def can_manage_resellers(user) -> bool:
    return is_super_admin(user) or has_group(user, "admin_resellers")

def is_admin(user) -> bool:
    return any([
        is_super_admin(user),
        can_manage_orders(user),
        can_manage_payments(user),
        can_manage_inventory(user),
        can_manage_resellers(user),
    ])

def build_admin_permissions(user) -> dict:
    return {
        "super_admin": is_super_admin(user),
        "orders": can_manage_orders(user),
        "payments": can_manage_payments(user),
        "inventory": can_manage_inventory(user),
        "resellers": can_manage_resellers(user),
    }

def can_view_orders(user) -> bool:
    return is_super_admin(user) or can_manage_orders(user) or can_manage_payments(user)