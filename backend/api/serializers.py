from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
# from django.db import transaction
# from rest_framework.fields import IntegerField

from djoser.serializers import (UserCreateSerializer, UserSerializer)
from rest_framework import serializers
from drf_extra_fields.fields import Base64ImageField
import base64
import uuid

from recipes.models import (FavoriteRecipe, Ingredient, IngredientAmount,
                            Recipe, ShoppingCart, Subscription, Tag)

User = get_user_model()


class UserCreateSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
        )
        extra_kwargs = {"password": {"write_only": True}}


class UserListSerializer(UserSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'password', 'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        return (self.context.get('request').user.is_authenticated
                and Subscription.objects.filter(
                    user=self.context.get('request').user,
                    author=obj).exists())


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = '__all__'


class IngredientAmountSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id',)
    name = serializers.ReadOnlyField(source='ingredient.name',)
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit',
    )

    class Meta:
        model = IngredientAmount
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    author = UserListSerializer(read_only=True)
    image = Base64ImageField(max_length=None, use_url=True)
    ingredients = serializers.SerializerMethodField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = ('author', 'name', 'image', 'text', 'cooking_time',
                  'tags', 'ingredients',
                  'is_favorite', 'is_in_shopping_cart')

    def get_is_favorite(self, obj):
        return (self.context.get('request').user.is_authenticated
                and FavoriteRecipe.objects.filter(
                    user=self.context.get('request').user,
                    favorite_recipe=obj).exists())

    def get_is_in_shopping_cart(self, obj):
        return (self.context.get('request').user.is_authenticated
                and ShoppingCart.objects.filter(
                    user=self.context.get('request').user,
                    recipe=obj).exists())

    def get_ingredients(self, obj):
        queryset = IngredientAmount.objects.filter(recipe=obj)
        return IngredientAmountSerializer(queryset, many=True).data


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr),
                               name=f'{uuid.uuid1()}.{ext}')

        return super().to_internal_value(data)


class IngredientEditSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ('id', 'amount')


class RecipeEditSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    image = Base64ImageField()
    # max_length=None, use_url=True
    ingredients = IngredientEditSerializer(
        many=True,
    )
    cooking_time = serializers.IntegerField(min_value=1)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True,
    )

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'tags', 'ingredients',
                  'cooking_time', 'text', 'image', 'author')

    def validate(self, data):
        for field in ['name', 'text']:
            if not data.get(field):
                raise serializers.ValidationError(
                    f'{field} - поле, обязательное для заполнения.'
                )
        ingredients = data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                'В рецепте должен быть хотя бы один ингредиент.'
            )
        if len(ingredients) != len(set([item['id'] for item in ingredients])):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.'
            )
        if not data.get('tags'):
            raise serializers.ValidationError('Укажите хотя бы один тег.')
        cooking_time = data.get('cooking_time')
        if cooking_time > 500 or cooking_time < 1:
            raise serializers.ValidationError(
                'Время приготовления блюда от 1 до 500 минут'
            )
        return data

    def create_ingredients(self, ingredients, recipe):
        IngredientAmount.objects.bulk_create([
            IngredientAmount(
                recipe=recipe,
                ingredient_id=ingredient.get('id'),
                amount=ingredient.get('amount'),
            ) for ingredient in ingredients])

    def create(self, validate_data):
        author = self.context.get('request').user
        ingredients = validate_data.pop('ingredients')
        tags = validate_data.pop('tags')
        recipe = Recipe.objects.create(author=author, **validate_data)
        recipe.tags.set(tags)
        self.create_ingredients(ingredients, recipe)
        return recipe

    def update(self, instance, validate_data):
        if 'ingredients' in validate_data:
            ingredients = validate_data.pop('ingredients')
            self.create_ingredients(ingredients, instance)
        if 'tags' in validate_data:
            instance.tags.set(validate_data.pop('tags'))
        return super().update(instance, validate_data)

    def to_representation(self, instance):
        return RecipeSerializer(instance, context=self.context).data


class SubscriptionRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'cooking_time')


class SubscriptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(
        source='author.id',
        read_only=True
    )
    username = serializers.CharField(
        source='author.username',
        read_only=True
    )
    email = serializers.CharField(
        source='author.email',
        read_only=True
    )
    first_name = serializers.CharField(
        source='author.first_name',
        read_only=True
    )
    last_name = serializers.CharField(
        source='author.last_name',
        read_only=True
    )
    recipes = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    recipes_count = serializers.ReadOnlyField(
        source='author.recipe.count'
    )

    class Meta:
        model = Subscription
        fields = ('id', 'username', 'email', 'first_name',
                  'last_name', 'recipes', 'is_subscribed',
                  'recipes_count')

    def validate(self, data):
        user = self.context.get('request').user
        author = self.context.get('author')
        if user == author:
            raise serializers.ValidationError(
                {'errors': 'Нельзя подписаться на самого себя.'}
            )
        if Subscription.objects.filter(user=user, author=author).exists():
            raise serializers.ValidationError(
                {'errors': 'Вы уже подписаны на этого автора.'}
            )
        return data

    def get_recipes(self, obj):
        recipes = obj.author.recipe.all()
        return SubscriptionRecipeSerializer(recipes, many=True).data

    def get_is_subscribed(self, obj):
        subscribe = Subscription.objects.filter(
            user=self.context.get('request').user,
            author=obj.author
        )
        if subscribe:
            return True
        return False


class FavoriteRecipeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='favorite_recipe.id',)
    name = serializers.ReadOnlyField(source='favorite_recipe.name',)
    image = serializers.CharField(
        source='favorite_recipe.image',
        read_only=True
    )
    cooking_time = serializers.ReadOnlyField(
        source='favorite_recipe.cooking_time',
    )

    class Meta:
        model = FavoriteRecipe
        fields = ('id', 'name', 'image', 'cooking_time')

    def validate(self, data):
        user = self.context.get('request').user
        recipe = self.context.get('recipe_id')
        if FavoriteRecipe.objects.filter(user=user,
                                         favorite_recipe=recipe).exists():
            raise serializers.ValidationError(
                {'errors': 'Рецепт уже добавлен в избранное.'}
            )
        return data


class ShoppingCartSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='recipe.id',)
    name = serializers.ReadOnlyField(source='recipe.name',)
    image = serializers.CharField(
        source='recipe.image',
        read_only=True
    )
    cooking_time = serializers.ReadOnlyField(
        source='recipe.cooking_time',
    )

    class Meta:
        model = ShoppingCart
        fields = ('id', 'name', 'image', 'cooking_time')

    def validate(self, data):
        user = self.context.get('request').user
        recipe = self.context.get('recipe_id')
        if ShoppingCart.objects.filter(user=user,
                                       recipe=recipe).exists():
            raise serializers.ValidationError(
                {'errors': "Рецепт уже добавлен в список покупок."}
            )
        return data
