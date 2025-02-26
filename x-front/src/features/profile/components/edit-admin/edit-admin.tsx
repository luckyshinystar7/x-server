import React, { useState } from 'react';
import { Button } from "@/common/components/ui/button";
import {
    Sheet,
    SheetContent,
    SheetTrigger,
    SheetHeader,
    SheetFooter,
    SheetTitle,
    SheetDescription,
} from '@/common/components/ui/sheet';
import { User } from '@/api/models/user';
import { useAlert } from '@/context/alert-context';
import { updateUserRole, UpdateUserRequest } from '@/api/auth-endpoints';
import { UpdateUserResponse } from '@/api/models/admin-responses';


interface EditAccountProps {
    user: User;
    onCancel: () => void;
    onRoleUpdate: (updateResponse: UpdateUserResponse) => void;
}

function EditRoleComponent({ user, onCancel, onRoleUpdate }: EditAccountProps) {
    const [role, setRole] = useState(user.role);
    const { showAlert } = useAlert();

    const handleRoleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        setRole(event.target.value);
    };

    const handleSaveChanges = async () => {
        try {
            const updateUserRequest: UpdateUserRequest = {
                role: role
            }
            const response = await updateUserRole(user.username, updateUserRequest);
            showAlert("Role changed successfully", "", "success");
            onRoleUpdate(response);
            onCancel();
        } catch (error) {
            onCancel();
            showAlert(error.message, "", "warning");
        }
    };


    return (
        <Sheet>
            <SheetTrigger asChild>
                <Button className='text-white'>Edit Role</Button>
            </SheetTrigger>
            <SheetContent>
                <div className="space-y-4 p-4 text-white">
                    <SheetHeader>
                        <SheetTitle>Edit User: {user.username}</SheetTitle>
                        <SheetDescription>Manage user role.</SheetDescription>
                    </SheetHeader>

                    <div className="space-y-1">
                        <select
                            id="role-select"
                            value={role}
                            onChange={handleRoleChange}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm bg-black focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                        >
                            <option value="user" className='text-center'>User</option>
                            <option value="admin" className='text-center'>Admin</option>
                        </select>
                    </div>

                    <SheetFooter className='flex container mx-auto justify-center space-y-2'>
                        <div className="md: grid grid-cols-2 gap-4">
                            <Button onClick={handleSaveChanges}>Save Role</Button>
                            <Button onClick={onCancel}>Cancel</Button>
                        </div>
                    </SheetFooter>
                </div>
            </SheetContent>
        </Sheet>
    );
}

export default EditRoleComponent;
