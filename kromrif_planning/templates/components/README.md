# Component Library

This directory contains reusable Django template components for the Kromrif Planning application. These components use Tailwind CSS for styling and support HTMX for interactive functionality.

## Available Components

### 1. Modal (`modal.html`)
Reusable modal dialog component with customizable size and close behavior.

**Example:**
```django
{% include 'components/modal.html' with modal_id='my-modal' modal_title='Edit Item' modal_size='lg' %}
```

**Parameters:**
- `modal_id`: Unique ID for the modal (required)
- `modal_title`: Title text for the modal header (optional)
- `modal_size`: 'sm', 'md', 'lg', 'xl' (default: 'md')
- `modal_closable`: Boolean, whether to show close button (default: true)
- `modal_backdrop_close`: Boolean, whether clicking backdrop closes modal (default: true)

### 2. Loading Spinner (`loading_spinner.html`)
Animated loading spinner with customizable size and text.

**Example:**
```django
{% include 'components/loading_spinner.html' with spinner_size='lg' spinner_text='Processing...' %}
```

**Parameters:**
- `spinner_size`: 'sm', 'md', 'lg' (default: 'md')
- `spinner_text`: Text to display next to spinner (optional)
- `spinner_color`: 'blue', 'indigo', 'gray', 'green', 'red' (default: 'indigo')

### 3. Alert (`alert.html`)
Alert component for success, error, warning, and info messages.

**Example:**
```django
{% include 'components/alert.html' with alert_type='success' alert_title='Success!' alert_message='Operation completed.' alert_dismissible=true %}
```

**Parameters:**
- `alert_type`: 'success', 'error', 'warning', 'info' (required)
- `alert_title`: Title text (optional)
- `alert_message`: Message text (required)
- `alert_dismissible`: Boolean, whether alert can be dismissed (default: false)
- `alert_icon`: Boolean, whether to show icon (default: true)

### 4. Button (`button.html`)
Customizable button component with multiple styles and icon support.

**Example:**
```django
{% include 'components/button.html' with btn_text='Save Changes' btn_type='primary' btn_icon='save' %}
```

**Parameters:**
- `btn_text`: Button text (required)
- `btn_type`: 'primary', 'secondary', 'danger', 'success', 'warning' (default: 'primary')
- `btn_size`: 'sm', 'md', 'lg' (default: 'md')
- `btn_icon`: Icon name (optional) - 'save', 'edit', 'delete', 'add', 'view', 'search', 'cancel'
- `btn_icon_position`: 'left', 'right' (default: 'left')
- `btn_disabled`: Boolean (default: false)
- `btn_loading`: Boolean (default: false)
- `btn_full_width`: Boolean (default: false)
- `btn_href`: URL for link button (optional)
- `btn_onclick`: JavaScript onclick handler (optional)
- `btn_submit`: Boolean, make it a submit button (default: false)
- `btn_id`: Button ID (optional)
- `btn_class`: Additional CSS classes (optional)

### 5. Form Field (`form_field.html`)
Comprehensive form field component with validation and help text.

**Example:**
```django
{% include 'components/form_field.html' with field=form.name field_type='text' field_required=true %}
```

**Parameters:**
- `field`: Django form field (required)
- `field_type`: 'text', 'email', 'password', 'textarea', 'select', 'checkbox', 'radio', 'file', 'color' (optional)
- `field_required`: Boolean (optional, overrides field.required)
- `field_help_text`: Custom help text (optional, overrides field.help_text)
- `field_placeholder`: Custom placeholder (optional)
- `field_label`: Custom label (optional, overrides field.label)
- `field_size`: 'sm', 'md', 'lg' (default: 'md')
- `field_full_width`: Boolean (default: true)
- `field_disabled`: Boolean (default: false)
- `field_readonly`: Boolean (default: false)
- `field_additional_classes`: Additional CSS classes for the input (optional)
- `field_wrapper_classes`: Additional CSS classes for the wrapper (optional)

### 6. Breadcrumb (`breadcrumb.html`)
Navigation breadcrumb component with customizable separators.

**Example:**
```django
{% include 'components/breadcrumb.html' with breadcrumbs=breadcrumb_items %}
```

Where `breadcrumb_items` is a list of dictionaries:
```python
breadcrumb_items = [
    {'text': 'Home', 'url': '/'},
    {'text': 'Guild Roster', 'url': '/roster/'},
    {'text': 'Ranks', 'url': None}  # No URL means current page
]
```

**Parameters:**
- `breadcrumbs`: List of breadcrumb items (required)
- `breadcrumb_home_icon`: Boolean, show home icon for first item (default: false)
- `breadcrumb_separator`: Custom separator (optional, default is chevron)

### 7. Card (`card.html`)
Flexible card component with header, body, and footer sections.

**Example:**
```django
{% include 'components/card.html' with card_title='Character Details' card_padding='lg' %}
    <!-- Card content goes here -->
{% endinclude %}
```

**Parameters:**
- `card_title`: Title for the card header (optional)
- `card_subtitle`: Subtitle text (optional)
- `card_padding`: 'none', 'sm', 'md', 'lg' (default: 'md')
- `card_shadow`: 'none', 'sm', 'md', 'lg', 'xl' (default: 'md')
- `card_border`: Boolean (default: false)
- `card_hover`: Boolean, add hover effect (default: false)
- `card_header_actions`: HTML for header action buttons (optional)
- `card_footer`: HTML for footer content (optional)
- `card_full_height`: Boolean (default: false)
- `card_clickable`: Boolean, make entire card clickable (default: false)
- `card_href`: URL if card is clickable (optional)
- `card_onclick`: JavaScript onclick if card is clickable (optional)

### 8. Pagination (`pagination.html`)
Django paginator-compatible pagination component.

**Example:**
```django
{% include 'components/pagination.html' with page_obj=page_obj %}
```

**Parameters:**
- `page_obj`: Django paginator page object (required)
- `pagination_size`: 'sm', 'md', 'lg' (default: 'md')
- `pagination_show_info`: Boolean, show result count info (default: true)
- `pagination_show_first_last`: Boolean, show first/last page links (default: true)
- `pagination_max_pages`: Number of page links to show (default: 7)
- `pagination_query_params`: Additional query parameters to preserve (optional)

### 9. HTMX Form (`htmx_form.html`)
HTMX-enabled form component with comprehensive configuration options.

**Example:**
```django
{% include 'components/htmx_form.html' with form_action='/api/characters/' form_target='#character-list' %}
    <!-- Form fields go here -->
{% endinclude %}
```

**Parameters:**
- `form_action`: URL to submit the form to (required)
- `form_target`: HTMX target selector (required)
- `form_method`: 'get', 'post', 'put', 'delete' (default: 'post')
- `form_swap`: HTMX swap method (default: 'innerHTML')
- `form_trigger`: HTMX trigger (default: 'submit')
- `form_indicator`: Loading indicator selector (optional)
- `form_confirm`: Confirmation message before submit (optional)
- `form_include`: Additional elements to include (optional)
- `form_encoding`: Form encoding type (optional)
- `form_boost`: Boolean, use HTMX boost (default: false)
- `form_push_url`: Boolean, push URL to history (default: false)
- `form_replace_url`: Boolean, replace URL in history (default: false)
- `form_reset`: Boolean, reset form after successful submit (default: false)
- `form_validate`: Boolean, use client-side validation (default: true)
- `form_class`: Additional CSS classes (optional)
- `form_id`: Form ID (optional)

## Usage Guidelines

### 1. Consistent Styling
All components use Tailwind CSS classes and follow consistent design patterns:
- Primary color: Indigo (`bg-indigo-600`, `text-indigo-600`, etc.)
- Success: Green (`bg-green-600`, `text-green-600`, etc.)
- Error/Danger: Red (`bg-red-600`, `text-red-600`, etc.)
- Warning: Yellow (`bg-yellow-600`, `text-yellow-600`, etc.)
- Info: Blue (`bg-blue-600`, `text-blue-600`, etc.)

### 2. Responsive Design
Components are built with responsive design in mind:
- Use `sm:`, `md:`, `lg:`, `xl:` prefixes for breakpoint-specific styles
- Mobile-first approach with progressive enhancement
- Grid layouts that adapt to screen size

### 3. Accessibility
Components include accessibility features:
- Proper ARIA labels and roles
- Keyboard navigation support
- Screen reader compatibility
- Focus management

### 4. HTMX Integration
Components are designed to work seamlessly with HTMX:
- Use `hx-*` attributes for dynamic behavior
- Support for common patterns like form submission, content loading, and modal interactions
- Proper loading states and error handling

## Best Practices

### 1. Component Composition
Combine components for complex UI patterns:
```django
{% include 'components/card.html' with card_title='Create Character' %}
    {% include 'components/htmx_form.html' with form_action='/characters/' form_target='#character-list' %}
        {% include 'components/form_field.html' with field=form.name %}
        {% include 'components/form_field.html' with field=form.character_class %}
        {% include 'components/button.html' with btn_text='Create' btn_type='primary' btn_submit=true %}
    {% endinclude %}
{% endinclude %}
```

### 2. Consistent Parameter Naming
Follow naming conventions:
- Component-specific parameters use the component name as prefix (e.g., `modal_size`, `btn_type`)
- Boolean parameters use clear names (e.g., `field_required`, `alert_dismissible`)
- Size parameters use consistent values: 'sm', 'md', 'lg', 'xl'

### 3. Performance Considerations
- Components are lightweight and load quickly
- CSS classes are utility-based for optimal caching
- JavaScript is minimal and focused on specific interactions

### 4. Testing Components
Test components with various parameter combinations:
- Test with and without optional parameters
- Verify responsive behavior across devices
- Test accessibility with keyboard navigation and screen readers
- Validate HTMX interactions in different browsers

## Migration Guide

### From Existing Templates
To migrate existing templates to use these components:

1. **Replace custom modals:**
   ```django
   <!-- Old -->
   <div class="modal">...</div>
   
   <!-- New -->
   {% include 'components/modal.html' with modal_id='my-modal' %}
   ```

2. **Replace form fields:**
   ```django
   <!-- Old -->
   <div class="form-field">
       <label>{{ form.name.label }}</label>
       {{ form.name }}
   </div>
   
   <!-- New -->
   {% include 'components/form_field.html' with field=form.name %}
   ```

3. **Replace buttons:**
   ```django
   <!-- Old -->
   <button class="btn btn-primary">Save</button>
   
   <!-- New -->
   {% include 'components/button.html' with btn_text='Save' btn_type='primary' %}
   ```

### Gradual Adoption
Components can be adopted gradually:
1. Start with new features using components
2. Replace high-traffic pages first
3. Update remaining templates during regular maintenance
4. Remove old component styles once migration is complete