from rest_framework import serializers

class RouteRequestSerializer(serializers.Serializer):

    start = serializers.CharField(

        help_text="Starting location",

        default="Dallas, TX"

    )

    end = serializers.CharField(

        help_text="Destination location",

        default="Chicago, IL"

    )