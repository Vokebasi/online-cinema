from django.contrib.auth import get_user_model, authenticate
from django.core.mail import send_mail
from rest_framework import serializers
from.tasks import send_activation_code
from config.settings import EMAIL_HOST_USER

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    password_confirm = serializers.CharField(max_length=100, required=True)
    class Meta:
        model = User
        fields = ('nickname', 'email', 'password', 'password_confirm')

    def validate_nickname(self, nickname):
        if User.objects.filter(nickname=nickname).exists():
            return serializers.ValidationError('This nickname is already token. Please choose another one')
        return nickname

    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email is already taken")
        return email

    def validate(self, data):
        password = data.get('password')
        password_confirm = data.pop('password_confirm')
        if not any(i for i in password if i.isdigit()):
            raise serializers.ValidationError('Password must contain at least on digit')
        if password != password_confirm:
            raise serializers.ValidationError("Passwords didnt match")
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.create_activation_code()
        send_activation_code.delay(user.email, user.activation_code)
        return user


class LoginSerializer(serializers.Serializer):
    nickname = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def validate_nickname(self, nickname):
        if not User.objects.filter(nickname=nickname).exists():
            raise serializers.ValidationError("User not found!")
        return nickname

    def validate(self, data):
        request = self.context.get('request')
        nickname = data.get('nickname')
        password = data.get('password')
        if nickname and password:
            user = authenticate(
                username = nickname,
                password = password,
                request = request)
            if not user:
                raise serializers.ValidationError('Bad credentials')
        else:
            raise serializers.ValidationError("Nickname and Password are Required")
        data['user'] = user
        return data


class ChangepasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(min_length=6, required=True)
    new_password = serializers.CharField(min_length=6, required=True)
    new_password_confirm = serializers.CharField(min_length=6, required=True)

    def validate_old_password(self, old_password):
        request = self.context.get('request')
        user = request.user
        if not user.check_password(old_password):
            raise serializers.ValidationError('Enter a valid password')
        return old_password

    def validate(self, attrs):
        new_pass1 = attrs.get('new_password')
        new_pass2 = attrs.get('new_password_confirm')
        if new_pass1 != new_pass2:
            raise serializers.ValidationError('Passwords did not match')
        return attrs

    def set_new_password(self):
        new_pass = self.validated_data.get('new_password')
        user = self.context.get('request').user
        user.set_password(new_pass)
        user.save()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, email):
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError('user not found!')
        return email

    def send_verification_email(self):
        email = self.validated_data.get('email')
        user = User.objects.get(email=email)
        user.create_activation_code()
        send_mail('Password Recovery!', f'Code for recovery is : {user.activation_code}', EMAIL_HOST_USER, [user.email])


class ForgotPasswordCompleteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True)
    password = serializers.CharField(min_length=6, required=True)
    password_confirmation = serializers.CharField(min_length=6, required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        code = attrs.get('code')
        password1 = attrs.get('password')
        password2 = attrs.get('password_confirmation')
        if not User.objects.filter(email=email, activation_code=code).exists():
            raise serializers.ValidationError('User not found!')
        if password1 != password2:
            raise serializers.ValidationError("Passwords did not match")
        return attrs

    def set_new_password(self):
        email = self.validated_data.get('email')
        password = self.validated_data.get('password')
        user = User.objects.get(email=email)
        user.set_password(password)
        user.save()
