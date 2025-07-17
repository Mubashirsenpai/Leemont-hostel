document.addEventListener('DOMContentLoaded', function() {
    // Mobile Menu Toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            menuToggle.classList.toggle('active');
        });
    }
    
    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-links ul li a').forEach(link => {
        link.addEventListener('click', () => {
            if (navLinks.classList.contains('active')) {
                navLinks.classList.remove('active');
                menuToggle.classList.remove('active');
            }
        });
    });
    
    // Sticky Header and Back to Top Button
    const header = document.querySelector('header');
    const backToTop = document.querySelector('.back-to-top');

    if (header || backToTop) {
        window.addEventListener('scroll', () => {
            if (header) {
                header.classList.toggle('scrolled', window.scrollY > 50);
            }
            if (backToTop) {
                backToTop.classList.toggle('active', window.scrollY > 300);
            }
        });
    }

    // Smooth scrolling for anchor links (if any are added later)
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // --- Cloudinary Upload Logic ---
    // IMPORTANT: Replace 'YOUR_CLOUDINARY_CLOUD_NAME' and 'YOUR_CLOUDINARY_UPLOAD_PRESET'
    // You will get these from your Cloudinary Dashboard.
    // The upload preset should be unsigned for direct browser uploads.
    const CLOUDINARY_CLOUD_NAME = 'dtbofqko6'; // Replace with your Cloud Name
    const CLOUDINARY_UPLOAD_PRESET = 'leemont_hostel_uploads'; // Replace with your Upload Preset (e.g., 'ml_default' or a custom one)

    // Helper function to handle file uploads to Cloudinary
    async function uploadFileToCloudinary(file, resourceType, statusElementId, hiddenInputId) {
        const statusElement = document.getElementById(statusElementId);
        const hiddenInput = document.getElementById(hiddenInputId);
        const submitButton = document.querySelector('button[type="submit"]'); // Get the form's submit button

        if (!file) {
            statusElement.textContent = 'No file selected.';
            statusElement.className = 'upload-status error';
            return null;
        }

        statusElement.textContent = `Uploading ${file.name}...`;
        statusElement.className = 'upload-status'; // Reset class
        if (submitButton) submitButton.disabled = true; // Disable submit button during upload

        const formData = new FormData();
        formData.append('file', file);
        formData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);

        try {
            const response = await fetch(`https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/${resourceType}/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.secure_url) {
                statusElement.textContent = `Uploaded ${file.name} successfully!`;
                statusElement.className = 'upload-status success';
                
                // For images, append to existing URLs (if any), separated by newline
                if (resourceType === 'image') {
                    const existingUrls = hiddenInput.value.split('\n').filter(url => url.trim() !== '');
                    existingUrls.push(data.secure_url);
                    hiddenInput.value = existingUrls.join('\n');
                } else { // For video, replace existing URL
                    hiddenInput.value = data.secure_url;
                }
                return data.secure_url;
            } else {
                statusElement.textContent = `Upload failed for ${file.name}: ${data.error ? data.error.message : 'Unknown error'}`;
                statusElement.className = 'upload-status error';
                return null;
            }
        } catch (error) {
            console.error('Upload error:', error);
            statusElement.textContent = `An error occurred during upload for ${file.name}.`;
            statusElement.className = 'upload-status error';
            return null;
        } finally {
            if (submitButton) submitButton.disabled = false; // Re-enable submit button
        }
    }

    // --- Event Listeners for File Inputs ---

    // Add Room / Edit Room Image Upload
    const uploadRoomImagesInput = document.getElementById('upload_images');
    if (uploadRoomImagesInput) {
        uploadRoomImagesInput.addEventListener('change', async (event) => {
            const files = event.target.files;
            if (files.length === 0) return;

            const hiddenInputId = 'images_cloudinary_urls';
            const hiddenInput = document.getElementById(hiddenInputId);
            hiddenInput.value = ''; // Clear existing URLs for new upload

            for (const file of files) {
                // Each image is uploaded sequentially
                await uploadFileToCloudinary(file, 'image', 'image_upload_status', hiddenInputId);
            }
        });
    }

    // Add Room / Edit Room Video Upload
    const uploadRoomVideoInput = document.getElementById('upload_video');
    if (uploadRoomVideoInput) {
        uploadRoomVideoInput.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            await uploadFileToCloudinary(file, 'video', 'video_upload_status', 'video_cloudinary_url');
        });
    }

    // Edit Hostel Details General Image Upload
    const uploadGeneralImagesInput = document.getElementById('upload_general_images');
    if (uploadGeneralImagesInput) {
        uploadGeneralImagesInput.addEventListener('change', async (event) => {
            const files = event.target.files;
            if (files.length === 0) return;

            const hiddenInputId = 'general_images_cloudinary_urls';
            const hiddenInput = document.getElementById(hiddenInputId);
            hiddenInput.value = ''; // Clear existing URLs for new upload

            for (const file of files) {
                await uploadFileToCloudinary(file, 'image', 'general_image_upload_status', hiddenInputId);
            }
        });
    }

    // Edit Hostel Details General Video Upload
    const uploadGeneralVideoInput = document.getElementById('upload_general_video');
    if (uploadGeneralVideoInput) {
        uploadGeneralVideoInput.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            await uploadFileToCloudinary(file, 'video', 'general_video_upload_status', 'general_video_cloudinary_url');
        });
    }

    // --- Form Submission Handling ---
    // Prevent form submission if uploads are still pending (though buttons are disabled)
    // This is a fallback and ensures the hidden fields are populated.

    const forms = ['addRoomForm', 'editRoomForm', 'editHostelDetailsForm'];
    forms.forEach(formId => {
        const form = document.getElementById(formId);
        if (form) {
            form.addEventListener('submit', function(event) {
                // Check if any upload is still in progress (e.g., if button re-enabled too quickly)
                const submitButton = event.submitter;
                if (submitButton && submitButton.disabled) {
                    event.preventDefault(); // Prevent submission
                    alert('Please wait for all uploads to complete before submitting.'); // Use a custom modal in a real app
                }
                // The hidden inputs should already be populated by the 'change' event listeners
                // so no further action is needed here for populating URLs.
            });
        }
    });

});
