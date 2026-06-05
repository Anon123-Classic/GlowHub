document.addEventListener('DOMContentLoaded', function() {
  var forms = document.querySelectorAll('form.needs-validation, form[data-validate]');
  forms.forEach(function(form) {
    form.addEventListener('submit', function(event) {
      var valid = true;
      var inputs = form.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea');
      inputs.forEach(function(input) {
        if (input.hasAttribute('required') && !input.value.trim()) {
          showError(input, 'This field is required.');
          valid = false;
        } else if (input.type === 'email' && input.value.trim() && !isValidEmail(input.value.trim())) {
          showError(input, 'Enter a valid email address.');
          valid = false;
        } else if ((input.name === 'phone' || input.name === 'customer_phone') && input.value.trim() && !input.value.match(/^\+254\d{9}$/)) {
          showError(input, 'Phone number must be in the format +254794760331');
          valid = false;
        } else if (input.name === 'password' || input.name === 'password1' || input.name === 'new_password1') {
          var pw = input.value;
          if (pw && pw.length < 6) {
            showError(input, 'Password too short.');
            valid = false;
          } else if (pw && isCommonPassword(pw)) {
            showError(input, 'Password is too common.');
            valid = false;
          }
        } else if (input.name === 'confirm_password' || input.name === 'password2' || input.name === 'new_password2') {
          var pwFieldName = input.name === 'confirm_password' ? 'password' : (input.name === 'password2' ? 'password1' : 'new_password1');
          var pw1 = form.querySelector('[name="' + pwFieldName + '"], [name="' + pwFieldName.replace('password1', 'password') + '"]');
          if (pw1 && input.value && pw1.value !== input.value) {
            showError(input, 'Passwords do not match.');
            valid = false;
          }
        } else if ((input.name === 'price' || input.name === 'amount' || input.name === 'duration' || input.name === 'expertise_years') && input.value.trim()) {
          var num = parseFloat(input.value);
          if (isNaN(num) || num < 0) {
            showError(input, 'Value must be a positive number.');
            valid = false;
          }
          if ((input.name === 'price' || input.name === 'amount') && num <= 0) {
            showError(input, 'Amount must be greater than zero.');
            valid = false;
          }
          if (input.name === 'duration' && num <= 0) {
            showError(input, 'Duration must be greater than zero.');
            valid = false;
          }
        } else {
          clearError(input);
        }
      });
      if (!valid) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
    form.querySelectorAll('input, select, textarea').forEach(function(input) {
      input.addEventListener('input', function() { clearError(input); });
      input.addEventListener('change', function() { clearError(input); });
    });
  });

  function showError(input, message) {
    input.classList.add('is-invalid');
    var feedback = input.parentElement.querySelector('.invalid-feedback');
    if (!feedback) {
      feedback = input.closest('.mb-3').querySelector('.invalid-feedback');
    }
    if (feedback) {
      feedback.textContent = message;
      feedback.style.display = 'block';
    } else {
      var div = document.createElement('div');
      div.className = 'invalid-feedback d-block';
      div.textContent = message;
      if (input.parentElement.classList.contains('mb-3')) {
        input.parentElement.appendChild(div);
      } else {
        input.closest('.mb-3').appendChild(div);
      }
    }
  }

  function clearError(input) {
    input.classList.remove('is-invalid');
    var feedback = input.parentElement.querySelector('.invalid-feedback');
    if (!feedback) {
      feedback = input.closest('.mb-3').querySelector('.invalid-feedback');
    }
    if (feedback) {
      feedback.style.display = 'none';
    }
  }

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function isCommonPassword(pw) {
    var common = ['password', '123456', '12345678', '123456789', 'qwerty', 'abc123', 'password1', '12345', '1234', '111111', '1234567', '123123', 'admin', 'letmein', 'welcome', 'monkey', 'dragon', 'master', 'passw0rd'];
    return common.indexOf(pw.toLowerCase()) !== -1;
  }
});
